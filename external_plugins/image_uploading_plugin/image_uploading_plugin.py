#!/usr/bin/env python3
"""
Smart-batched uploader for Tapis Files.
Now uses a JSON config file instead of environment variables.

Required JSON keys:
  - "token": Tapis access token string
  - "dir":   "{system_id}/{dest_dir}" (e.g., "ascend-tapis/users/you/inbox")
"""

import os
import json
import toml
import time
import signal
import threading
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from PIL import Image  # requires: pip install Pillow

import zmq
import logging
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
from ctevents.ctevents import socket_message_to_typed_event, send_terminate_plugin_fb_event, send_monitor_power_start_fb_event
from ctevents import ImageStoredEvent, ImageDeletedEvent, ImageScoredEvent, PluginTerminatingEvent, PluginTerminateEvent

log_level = os.environ.get("IMAGE_UPLOADING_LOG_LEVEL", "INFO")
logger = logging.getLogger("Image Uploading Plugin")
if log_level == "DEBUG":
    logger.setLevel(logging.DEBUG)
elif log_level == "INFO":
    logger.setLevel(logging.INFO)
elif log_level == "WARN":
    logger.setLevel(logging.WARN)
elif log_level == "ERROR":
    logger.setLevel(logging.ERROR)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ----------------------- CONFIG -----------------------
UPLOAD_THRESHOLD_FILE = os.environ.get('TRAPS_UPLOAD_FILE', '/traps-upload.toml')
PORT = os.environ.get('IMAGE_UPLOADING_PLUGIN_PORT', 6013)
BASE_URL = os.environ.get("BASE_URL", "https://tacc.tapis.io")

# Path to JSON config file (edit this path)
TOKEN = os.environ.get("JWT")
SYSTEM_ID = os.environ.get("SYSTEM_ID")
DEST_DIR = os.environ.get("DEST_DIR")

WATCH_DIR = os.environ.get("WATCH_DIR", "/images")
RECURSIVE = False

# batching triggers (flush when any trips)
BATCH_MAX_AGE   = 3600              # seconds since first file added
BATCH_MAX_FILES = 2            # max files in a batch
BATCH_MAX_BYTES = 30000 * 1024**2    # 300 MB total batch size

# upload behavior
WORKERS = 8
STABILITY_SECONDS = 3.0           # wait for file to stop growing
RETRY_MAX = 3
RETRY_BACKOFF = 2.0               # seconds * (2**attempt)

# ignore rules
IGNORE_SUFFIXES = (".tmp", ".partial", ".crdownload", ".swp", ".swx")
IGNORE_PREFIXES = (".",)  # e.g., .DS_Store, .gitkeep
# ------------------------------------------------------

# internal state
_executor = ThreadPoolExecutor(max_workers=WORKERS)
_queued_events = set()
_event_lock = threading.Lock()

_batch_lock = threading.Lock()
_batch_files = []        # list of (path, size)
_batch_bytes = 0
_batch_first_ts = None
_flusher_stop = threading.Event()

# ---------------- core utils ----------------
def is_stable(path: str, wait: float = STABILITY_SECONDS) -> bool:
    if not os.path.isfile(path):
        return False
    try:
        size1 = os.path.getsize(path)
    except OSError:
        return False
    time.sleep(wait)
    if not os.path.isfile(path):
        return False
    try:
        size2 = os.path.getsize(path)
    except OSError:
        return False
    return size1 == size2 and size1 > 0

def is_valid_image(path: str) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
        return True
    except Exception as e:
        logger.warning(f"[INVALID IMG] {path}: {e}")
        return False

def parse_dir(combined: str):
    """
    Parse "{system_id}/{dest_dir...}" into (system_id, "/dest_dir...")
    Accepts optional leading slash.
    """
    if not combined or not isinstance(combined, str):
        raise ValueError("config 'dir' must be a non-empty string")
    s = combined.strip().lstrip("/")  # drop leading slash if present
    parts = s.split("/", 1)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("config 'dir' must look like 'system_id/path/to/dest_dir'")
    system_id = parts[0]
    dest_dir = "/" + parts[1]        # ensure leading slash
    return system_id, dest_dir

def run_upload(filepath: str) -> bool:
    """Upload a single file via Tapis Files API. Returns True on success."""
    assert TOKEN != "" and SYSTEM_ID != "" and DEST_DIR != ""
    fp = os.path.abspath(filepath)

    bn_enc = urllib.parse.quote(os.path.basename(fp))
    url = f"{BASE_URL.rstrip('/')}/v3/files/ops/{SYSTEM_ID}{DEST_DIR}/{bn_enc}"

    args = [
        "curl", "-sS", "--fail-with-body",
        "-X", "POST",
        "-H", f"X-Tapis-Token: {TOKEN}",
        "--form", f"file=@{fp}",
        url,
    ]
    logger.info(f'Uploading with command: {args}')

    attempt = 0
    while True:
        attempt += 1
        res = subprocess.run(args, capture_output=True, text=True)
        if res.returncode == 0:
            logger.info(f"[OK] {fp}")
            return True
        logger.warning(f"[ERR] {fp} (exit {res.returncode})\n{res.stderr or res.stdout}")
        if attempt >= RETRY_MAX:
            logger.warning(f"[GIVEUP] {fp} after {RETRY_MAX} attempts")
            return False
        time.sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))

# -------------- batching helpers --------------
def _batch_add(path: str):
    global _batch_first_ts, _batch_bytes
    size = os.path.getsize(path)
    with _batch_lock:
        if not _batch_files:
            _batch_first_ts = time.time()
        _batch_files.append((path, size))
        _batch_bytes += size
    logger.info(f"[QUEUE] Added to batch: {path} ({size} bytes)")

def _batch_ready() -> bool:
    with _batch_lock:
        if not _batch_files:
            return False
        age_ok = (time.time() - _batch_first_ts) >= BATCH_MAX_AGE
        count_ok = len(_batch_files) >= BATCH_MAX_FILES
        size_ok = _batch_bytes >= BATCH_MAX_BYTES
    return age_ok or count_ok or size_ok

def _take_batch():
    global _batch_files, _batch_bytes, _batch_first_ts
    with _batch_lock:
        items = list(_batch_files)
        _batch_files = []
        _batch_bytes = 0
        _batch_first_ts = None
    return items

def _flush_now():
    start_ts = time.time()

    items = _take_batch()
    if not items:
        return

    total_bytes = sum(s for _, s in items)
    logger.info(f"[BATCH] Flushing {len(items)} files, total {total_bytes} bytes")

    futs = []
    for path, _ in items:
        futs.append(_executor.submit(run_upload, path))

    ok = 0
    for f in futs:
        try:
            if f.result():
                ok += 1
        except Exception as e:
            logger.warning(f"[BATCH ERR] {e}")

    end_ts = time.time()
    elapsed = end_ts - start_ts
    logger.info(f"[BATCH] Done: {ok}/{len(items)} successful in {elapsed:.2f} seconds")

def _flusher_loop():
    while not _flusher_stop.is_set():
        if _batch_ready():
            _flush_now()
        _flusher_stop.wait(0.5)
    if _batch_files:
        _flush_now()

# -------------- event intake --------------
def enqueue_for_batch(filepath: str) -> None:
    bn = os.path.basename(filepath)
    if bn.startswith(IGNORE_PREFIXES) or filepath.lower().endswith(IGNORE_SUFFIXES):
        return

    with _event_lock:
        if filepath in _queued_events:
            return
        _queued_events.add(filepath)

    def task():
        try:
            if not is_stable(filepath):
                time.sleep(STABILITY_SECONDS)
                if not is_stable(filepath):
                    logger.info(f"[SKIP] Not stable: {filepath}")
                    return
            if not os.path.isfile(filepath):
                return
            if not is_valid_image(filepath):
                logger.info(f"[SKIP] Invalid/truncated image: {filepath}")
                return
            _batch_add(filepath)
        finally:
            with _event_lock:
                _queued_events.discard(filepath)

    _executor.submit(task)

# ------------------- Main -------------------
def _handle_term(signum, frame):
    _flusher_stop.set()

def get_socket():
    context = zmq.Context()
    return get_plugin_socket(context, PORT)  

def get_upload_thresholds():
    if os.path.exists(UPLOAD_THRESHOLD_FILE):
        with open(UPLOAD_THRESHOLD_FILE, 'r') as f:
            return toml.load(f).get('thresholds')

def main():
    global socket
    socket = get_socket()

    flusher = threading.Thread(target=_flusher_loop, daemon=True)
    flusher.start()

    logger.info(f"Watching {WATCH_DIR} (batched) → {SYSTEM_ID}{DEST_DIR}")
    logger.info(f"Batch triggers: age≥{BATCH_MAX_AGE}s OR files≥{BATCH_MAX_FILES} OR bytes≥{BATCH_MAX_BYTES}.")
    logger.info(f"Base URL: {BASE_URL}")

    upload_threshold = get_upload_thresholds()
    upload_list = set()
    done = False
    while not done:
        try:
            message = get_next_msg(socket)
        except zmq.error.Again:
            logger.debug(f"Got a zmq.error.Again; i.e., waited {SOCKET_TIMEOUT} ms without getting a message")
            continue
        except Exception as e:
            logger.debug(f"Got exception from get_next_msg; type(e): {type(e)}; e: {e}")
            done = True 
            continue
        if not message:
            logger.info("No message found in get_next_msg")

        logger.info("Got a message from the event socket - Image uploader")
        event = socket_message_to_typed_event(message)

        if isinstance(event, ImageScoredEvent):
            logger.info(f'Image scored event received')
            uuid = event.ImageUuid().decode('utf-8')
            for i in range(event.ScoresLength()):
                label = event.Scores(i).Label().decode('utf-8')
                prob = event.Scores(i).Probability()
                if not upload_threshold:
                    logger.info(f'Image scored and no thresholds found. Waiting for image store decision before adding to batch.')
                    upload_list.add(uuid)
                    break
                elif label in upload_threshold and prob > upload_threshold[label]:
                    logger.info(f'Image score above upload threshold. Waiting for image store decision before adding to batch.')
                    upload_list.add(uuid)
                    break
        elif isinstance(event, ImageStoredEvent):
            uuid = event.ImageUuid().decode('utf-8')
            if uuid not in upload_list:
                logger.info(f'Image stored but score is below the upload threshold. Skipping upload.')
                continue
            ext = event.ImageFormat().decode('utf-8')
            timestamp = event.EventCreateTs().decode('utf-8')
            destination = event.Destination().decode('utf-8')
            image_path = f'{WATCH_DIR}/{uuid}.{ext}'
            logger.info(f"Image stored {uuid} {timestamp} {destination} {image_path}")
            enqueue_for_batch(image_path)
            upload_list.remove(uuid)

        elif isinstance(event, PluginTerminateEvent):
            logger.info('received PluginTerminateEvent')
            done = True

    _flusher_stop.set()
    flusher.join()
    _executor.shutdown(wait=True)
    send_quit_command(socket)

if __name__ == "__main__":
    logger.info("Image uploading plugin starting...")
    main()
    logger.info("Image uploading plugin exiting...")
