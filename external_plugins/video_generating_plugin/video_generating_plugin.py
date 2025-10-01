import os
import zmq
from ctevents import MonitorPowerStartEvent, MonitorPowerStopEvent, PluginTerminateEvent
from ctevents.ctevents import socket_message_to_typed_event, send_terminate_plugin_fb_event, send_monitor_power_start_fb_event
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
import logging
from subprocess import Popen, run, PIPE, STDOUT
from math import ceil
import yaml
import requests

log_level = os.environ.get("VIDEO_GENERATING_LOG_LEVEL", "INFO")
input_video_path = os.environ.get("INPUT_VIDEO_PATH", "/example_video.mp4")
use_ground_truth_url = os.environ.get("USE_CUSTOM_GROUND_TRUTH_FILE_URL", False)
ground_truth_url = os.environ.get("CUSTOM_GROUND_TRUTH_URL")
ground_truth_file = os.environ.get("GROUND_TRUTH_FILE", "/ground_truth.yml")
device = os.environ.get("DEVICE", "/dev/video0")
mode = os.environ.get("MODE", "device")

logger = logging.getLogger("Image Generating Plugin")
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

def get_socket():
    """
    This function creates the zmq socket object and generates the event-engine plugin socket
    for the port configured for this plugin.
    """
    # get the port assigned to the Image Generating plugin
    PORT = os.environ.get('VIDEO_GENERATING_PLUGIN_PORT', 6003)
    # create the zmq context object
    context = zmq.Context()
    socket = get_plugin_socket(context, PORT)
    socket.RCVTIMEO = 100 # in milliseconds
    return socket

def get_video_duration():
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_video_path], stdout=PIPE, stderr=STDOUT)
    duration = ceil(float(result.stdout))
    logger.info(f'{input_video_path} has a duration of {duration} seconds')
    return duration


def load_ground_truth():
    video_info = {}
    try:
        if use_ground_truth_url:
            logger.info(f"Retrieving custom ground truth file: {ground_truth_url}")
            response = requests.get(ground_truth_url)
            if response.status_code == 200:
                yml_content = response.content.decode('utf-8').splitlines()
                video_info = yaml.safe_load(yml_content)
        else:
            with open(ground_truth_file, 'r') as f:
                video_info = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {ground_truth_file}")
    except Exception as e:
        logger.error(f'An error occurred: {e}')
    video_info['duration'] = get_video_duration()
    OUTPUT_DIR = os.environ.get('TRAPS_VIDEO_OUTPUT_PATH', '/video_info')
    video_info_file = os.path.join(OUTPUT_DIR, 'video_info.yaml')
    with open(video_info_file, 'w') as f:
        yaml.dump(video_info, f)
    logger.info(f'Updating {OUTPUT_DIR}/video_info.yaml')

def monitor_generating_power():
    """
    This function is used to initiate the power monitoring event, if the monitoring flag is set.
    """
    monitor_flag = os.getenv('MONITOR_POWER')
    pid = [os.getpid()]
    monitor_type = [1]
    monitor_seconds = 0
    if monitor_flag:
        send_monitor_power_start_fb_event(socket, pid, monitor_type, monitor_seconds)
        logger.info(f"Monitoring image generating power")

def is_v4l2loopback_available():
    out = run(['v4l2-ctl', '-d', device, '--all'], capture_output=True)
    for line in out.stdout.decode().splitlines():
        if line.strip().lower().startswith('driver name') and 'v4l2 loopback' in line.lower():
            return True
    return False

def stream_file_to_device(input_video_path):
    logger.info(f'starting video device stream to {device}')
    return Popen(['ffmpeg', '-re', '-stream_loop', '-1', '-i', input_video_path, '-f', 'v4l2', '-pix_fmt', 'yuv420p', device])


def process_video(input_video_path, ground_truth):
    """
    Main function that starts a video stream on a /dev/video device
    """
    logger.info(f"The input video path specified by the user:{input_video_path}")
    if is_v4l2loopback_available():
        return stream_file_to_device(input_video_path)
    else:
        logger.warning('v4l2loopback not available for {device}. Shutting down')

def main():
    global socket
    ground_truth = load_ground_truth()
    stream_proc = None
    if mode == 'device':
        monitor_generating_power()
        stream_proc = process_video(input_video_path, ground_truth)
    done = False
    while not done:
        socket = get_socket()
        try:
            message = get_next_msg(socket)
        except zmq.error.Again:
            logger.debug(f"Got a zmq.error.Again; i.e., waited {SOCKET_TIMEOUT} ms without getting a message")
            continue
        except Exception as e:
            logger.debug(f"Got exception from get_next_msg; type(e): {type(e)}; e: {e}")
            done = True
            logger.info("Video generating plugin stopping due to timeout limit...")
            continue
        if not message:
            logger.info("No message found in get_next_msg")

        event = socket_message_to_typed_event(message)
        logger.info(f"Got a message from the event socket of type: {type(event)}")
        if isinstance(event, PluginTerminateEvent):
            logging.info('received PluginTerminateEvent')
            done = True

    if stream_proc:
        stream_proc.kill()
    send_quit_command(socket)

if __name__ == '__main__':
    logger.info("Video generating plugin starting...")
    main()
    logger.info("Video generating plugin exiting...")
