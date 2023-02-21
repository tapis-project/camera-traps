import json
import os
import ctevents
from events import get_plugin_socket, get_next_msg, send_quit_command

import zmq
PORT = os.environ.get('IMAGE_GENERATING_PLUGIN_PORT', 6000)
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
    f = get_next_msg(socket)
    print(f"just got message {total_messages}; contents: {msg_bytes}")
    total_messages += 1
    
    if total_messages == 11:
        done = True

#f = open('/example_images/detections.json')

data = json.load(f)
for i in data['images'] :
  for j in i['detections']:
    if(j['category']=="1" and i['max_detection_conf']==j['conf']):
      print(i["file"],j['conf'])


f.close()
