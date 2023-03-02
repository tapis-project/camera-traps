import json
import os
from ctevents import bytes_to_typed_event
from events import get_plugin_socket, get_next_msg, send_quit_command

import zmq
PORT = os.environ.get('IMAGE_GENERATING_PLUGIN_PORT', 6000)
base_path = os.environ('IMAGE_PATH')

def get_socket():
    # create the zmq context object
    context = zmq.Context()
    return get_plugin_socket(context, PORT)  

socket = get_socket()
done = False
total_messages = 1
while not done:
    # get the next message
    
    print(f"waiting on message: {total_messages}")
    m = get_next_msg(socket)
    e = bytes_to_typed_event(m)
    print(f"just got message {total_messages}; contents: {msg_bytes}")
    total_messages += 1
    
    if total_messages == 11:
        done = True

f = open('/example_images/detections.json')

data = json.load(f)
for i in data['images'] :
  for j in i['detections']:
    if(j['category']=="1" and i['max_detection_conf']==j['conf']):
      print(i["file"],j['conf'])


f.close()
