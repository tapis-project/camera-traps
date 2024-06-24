import os
import zmq
import logging
import json
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
from ctevents.ctevents import socket_message_to_typed_event
from ctevents import ImageStoredEvent, ImageDeletedEvent, ImageScoredEvent
from ctevents.gen_events.ImageLabelScore import ImageLabelScore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Oracle Monitor")
PORT = int(os.environ.get('ORACLE_PLUGIN_PORT', 6011))
OUTPUT_DIR = os.environ.get('TRAPS_ORACLE_OUTPUT_PATH', "/output/")
file_name = "image_mapping.json"
SOCKET_TIMEOUT = 2000

def get_socket():
    context = zmq.Context()
    return get_plugin_socket(context, PORT)  

def update_json(uuid,updated_data):
    output_file = os.path.join(OUTPUT_DIR, file_name)
    with open(output_file, 'r+') as file:
        try:
            mapping = json.load(file)
            print(mapping)
        except json.JSONDecodeError:

            print("error")
    
        if uuid in mapping:
            for field,value in enumerate(updated_data):
                print(field,value,updated_data)
                mapping[uuid][field].update(updated_data)
                print(mapping)
        file.seek(0)
        json.dump(mapping,file)
        file.truncate()

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
        
        if isinstance(event, ImageScoredEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            # for i in range(event.ScoresLength()):
            #     label = event.Scores(i).Label().decode('utf-8')
            timestamp = event.EventCreateTs().decode('utf-8').strip("'")
            #logger.info(f"Inside scoring {uuid}, {timestamp}")
            update_json(uuid, {"image_scoring_timestamp": timestamp})

        elif isinstance(event, ImageStoredEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            timestamp = event.EventCreateTs().decode('utf-8').strip("'")
            destination = event.Destination().decode('utf-8').strip("'")
            #logger.info("Image stored", {uuid},{timestamp},{destination})
            update_json(uuid, {"image_store_delete_time": timestamp, "image_stored": "True", "image_deleted": "False"})

        elif isinstance(event, ImageDeletedEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            timestamp = event.EventCreateTs().decode('utf-8').strip("'")
            #logger.info("Image stored", {uuid},{timestamp},"Deleted")
            update_json(uuid, {"image_store_delete_time": timestamp, "image_stored": "False", "image_deleted": "True"})

        else:
            logger.info(event)

if __name__ == '__main__':
    main()
