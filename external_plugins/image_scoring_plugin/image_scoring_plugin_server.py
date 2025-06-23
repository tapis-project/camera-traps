import json
import os
import cv2
import base64
import numpy as np
import requests
from io import BytesIO
from ctevents.ctevents import socket_message_to_typed_event, send_image_scored_fb_event, send_monitor_power_start_fb_event,send_terminate_plugin_fb_event
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
from ctevents import PluginTerminateEvent, ImageReceivedEvent
import sys
import zmq
import logging

log_level = os.environ.get("IMAGE_SCORING_LOG_LEVEL", "INFO")
logger = logging.getLogger("Image Scoring Plugin")
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


DEFAULT_BOX_THICKNESS = 4
DEFAULT_BOX_EXPANSION = 0
CROP_IMAGE = (os.getenv('CROP_IMAGE') == 'true')
DETECTIONS = (os.getenv('DETECTIONS') == 'true')
# Whether to force image resizing to a (square) integer size (not recommended to change this)
# None means no resizing.
IMAGE_SIZE = None


PORT = os.environ.get('IMAGE_SCORING_PLUGIN_PORT', 6000)
base_path = os.environ.get('IMAGE_PATH')
image_path_prefix = os.environ.get('IMAGE_FILE_PREFIX', '')

# whether to cache the detector or to use the old method "load_and_run_detector()" method on each image
# export any other value to use the old method.
DEFAULT_MODE = 'cache_detector'
MODE = os.environ.get('MODE', DEFAULT_MODE)

SERVER_HOST = os.environ.get('SERVER_HOST', 'localhost')
SERVER_PORT = os.environ.get('SERVER_PORT', '8000')


def get_socket():
    # create the zmq context object
    context = zmq.Context()
    return get_plugin_socket(context, PORT)  

def get_image_file_path(image_uuid, image_format):
   """
   Returns the path on the file system to an image with the given uuid and format.
   """
   if type(image_uuid) == bytes:
      image_uuid = image_uuid.decode('utf-8')
   if type(image_format) == bytes:
      image_format = image_format.decode('utf-8')
   # also convert to lower case since that seems to be what the image received plugin is doing:
   # TODO -- should not have to do this.
   image_format = image_format.lower()
   return f"{base_path}/{image_path_prefix}{image_uuid}.{image_format}"

def monitor_scoring_power(socket):
    monitor_flag = os.getenv('MONITOR_POWER')
    pid = [os.getpid()]
    monitor_type = [1]
    monitor_seconds = 0
    if monitor_flag:
        logger.debug(f"Sending a power monitor start event for the following data: PID: {pid}; monitor_type: {monitor_type}; duration: {monitor_seconds}")
        send_monitor_power_start_fb_event(socket, pid, monitor_type, monitor_seconds)
        logger.info(f"Message sent to monitor power for image scoring plugin")

def main():
    logger.info("top of main.")
    socket = get_socket()
    logger.debug("got zmq socket.")
    monitor_scoring_power(socket)
    done = False
    total_messages = 0

    while not done:
        # get the next message
        logger.debug(f"waiting on message: {total_messages + 1}")
        m = get_next_msg(socket)
        e = socket_message_to_typed_event(m)

        total_messages += 1
        logger.info(f"just got message {total_messages}; type(e): {type(e)}")
        # TODO: we could check if e is not an image_received event, skip it....
        
        # - find the image on the file system, (the image path)
        if isinstance(e, PluginTerminateEvent):
            logger.info(f"Received Terminate event * and shutting down image scoring plugin")
            send_quit_command(socket)
            sys.exit()
        if not isinstance(e, ImageReceivedEvent):
            logger.error(f"Got an unexpected event of type {type(e)}; message was: {e}; ignoring message.")
            continue
        image_uuid = e.ImageUuid()
        if type(image_uuid) == bytes:
           image_uuid = image_uuid.decode('utf-8')
        image_format = e.ImageFormat()
        if type(image_format) == bytes:
            image_format = image_format.decode('utf-8')
        image_file_path = get_image_file_path(image_uuid, image_format)                
        # score the image
        logger.debug(f"Scoring image: {image_file_path}")
        img = cv2.imread(image_file_path)
        _, buffer = cv2.imencode(".jpg", img)
        img_bytes = base64.b64encode(buffer).decode("utf-8")
        payload = {
            "image": img_bytes,
        }
        response = requests.post(f"{SERVER_HOST}:{SERVER_PORT}/predict", json=payload)
        if response.status_code == 200:
            data = response.json()
            results = data["detections"]
        else:
            results = None
        scores = []
        
        if not results:
            scores.append({"image_uuid": image_uuid, "label": "empty", "probability": 0.0})
        else:
            for r in results:
                # Each score object should have the format: 
                #     {"image_uuid": image_uuid, "label": "animal", "probability": 0.85}
                # Each result returned from detector is a dictionary with `category` and `conf`
                # If an image contains multiple detection, we need to append muplitple label and probability for each image.
                scores.append({"image_uuid": image_uuid, "label": r['category'], "probability": r['conf']})
        logger.info(f"Sending image scored event with the following scores: {scores}") 
        send_image_scored_fb_event(socket, image_uuid, image_format, scores)
        logger.info(f"Image Scoring Plugin processing for message {total_messages} complete.")        



if __name__ == "__main__":
   main()
