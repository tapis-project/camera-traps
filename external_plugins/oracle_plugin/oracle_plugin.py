import os
import zmq
import logging
import csv
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
from ctevents.ctevents import socket_message_to_typed_event
from ctevents import ImageStoredEvent, ImageDeletedEvent, ImageScoredEvent
from ctevents.gen_events.ImageLabelScore import ImageLabelScore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Oracle Monitor")

PORT = int(os.environ.get('ORACLE_PLUGIN_PORT', 6011))
OUTPUT_DIR = os.environ.get('TRAPS_ORACLE_OUTPUT_PATH', "/output/")
file_name = "ground_truth.csv"
SOCKET_TIMEOUT = 2000

def get_socket():
    context = zmq.Context()
    return get_plugin_socket(context, PORT)  

def main():
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
            logger.info("Oracle monitoring plugin stopping due to timeout limit...")
            continue

        logger.info("Got a message from the event socket - Oracle monitor check")
        event = socket_message_to_typed_event(message)
        output_file = os.path.join(OUTPUT_DIR, file_name)

        if not os.path.exists(output_file):
            with open(output_file, 'w', newline='') as file:
                mapping = csv.writer(file)
                field = ["UUID", "Scores", "timestamp", "UUID", "destination", "timestamp"]
                mapping.writerow(field)

        if isinstance(event, ImageScoredEvent):
            with open(output_file, 'a', newline='') as file:
                mapping = csv.writer(file)
                uuid = event.ImageUuid()
                scores = event.ScoresLength()
                #sc = event.Scores(scores)
                timestamp = event.EventCreateTs()
                logger.info(f"Inside scoring {uuid}, {scores}, {timestamp}")
                mapping.writerow([uuid, scores, timestamp])

        elif isinstance(event, ImageStoredEvent):
            with open(output_file, 'a', newline='') as file:
                mapping = csv.writer(file)
                uuid = event.ImageUuid()
                timestamp = event.EventCreateTs()
                destination = event.Destination()
                logger.info("Image stored")
                mapping.writerow([uuid, destination, timestamp])

        elif isinstance(event, ImageDeletedEvent):
            logger.info("Image deleted")

        else:
            logger.info(event)

if __name__ == '__main__':
    main()
