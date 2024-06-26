import os
import zmq
import logging
import json
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
from ctevents.ctevents import socket_message_to_typed_event
from ctevents import ImageStoredEvent, ImageDeletedEvent, ImageScoredEvent, ImageReceivedEvent, PluginTerminateEvent


log_level = os.environ.get("ORACLE_LOG_LEVEL", "INFO")
logger = logging.getLogger("Oracle Monitor")
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


PORT = int(os.environ.get('ORACLE_PLUGIN_PORT', 6011))
OUTPUT_DIR = os.environ.get('TRAPS_ORACLE_OUTPUT_PATH', "/output/")
file_name = "image_mapping.json"
final_file = "image_mapping_final.json"
SOCKET_TIMEOUT = 2000

def get_socket():
    context = zmq.Context()
    return get_plugin_socket(context, PORT)  

def update_json(uuid,updated_data):
    output_file = os.path.join(OUTPUT_DIR, file_name)
    output_file2 = os.path.join(OUTPUT_DIR, final_file)
    try:
        with open(output_file2, 'r') as file2:
            try:
                existing_data = json.load(file2)
            except json.JSONDecodeError:
                logger.error(f"JSON decoding error for {output_file2}")
                existing_data = {}
    except FileNotFoundError:
        logger.error(f"File not found: {output_file2}")
        existing_data = {}   

    if uuid not in existing_data:
        logger.info(f"Fetching - {uuid} from {output_file}")
        try:
            with open(output_file, 'r') as file:
                try:
                    mapping = json.load(file)
                except json.JSONDecodeError:
                    logger.error(f"JSON loading Error for {output_file}")
                    mapping = {}
                existing_data[uuid] = mapping.get(uuid,{uuid : [{"UUID": uuid}]})
        except FileNotFoundError:
            logger.error(f"File {output_file} not found")

        # file.seek(0)
        # json.dump(mapping,file)
        # file.truncate()  
    for field in existing_data[uuid]:
        for key,value in updated_data.items():
            field[key] = value           
    with open(output_file2, "w") as file2: 
        json.dump(existing_data, file2, indent=2)

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
        if not message:
            logger.info("No message found in get_next_msg")

        logger.info("Got a message from the event socket - Oracle monitor check")
        event = socket_message_to_typed_event(message)

        if isinstance(event, ImageReceivedEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            timestamp = event.EventCreateTs().decode('utf-8').strip("'")
            logger.info(f"Image received {uuid}, {timestamp}")
            update_json(uuid, {"image_receiving_timestamp": timestamp})

        elif isinstance(event, ImageScoredEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            scores = [] # event.ScoresLength()
            for i in range(event.ScoresLength()):
                label = event.Scores(i).Label().decode('utf-8')
                prob = event.Scores(i).Probability()
                scores.append({"label": label, "probability": prob})
            timestamp = event.EventCreateTs().decode('utf-8').strip("'")
            logger.info(f"Inside scoring {uuid}, {scores}, {timestamp}")
            update_json(uuid, {"image_scoring_timestamp": timestamp, "score" : scores})

        elif isinstance(event, ImageStoredEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            timestamp = event.EventCreateTs().decode('utf-8')
            destination = event.Destination().decode('utf-8').strip("'")
            logger.info(f"Image stored {uuid},{timestamp},{destination}")
            update_json(uuid, {"image_store_delete_time": timestamp, "image_decision": destination})

        elif isinstance(event, ImageDeletedEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            print("timestamp inside image delete",{event.EventCreateTs()} )
            timestamp = event.EventCreateTs().decode('utf-8')
            logger.info(f"Image deleted {uuid},{timestamp}")
            update_json(uuid, {"image_delete_time": timestamp, "image_decision": "Deleted"})

        elif isinstance(event,PluginTerminateEvent):
            uuid = event.ImageUuid().decode('utf-8').strip("'")
            plugin_name = event.TargetPluginName()
            logger.info(f"Terminate {uuid},{plugin_name}")

        else:
            logger.info(event)
        

if __name__ == '__main__':
    logger.info("Oracle plugin starting...")
    main()

    logger.info("Oracle plugin exiting...")
