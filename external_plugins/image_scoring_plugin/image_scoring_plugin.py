import json
import os
from ctevents import bytes_to_typed_event, send_image_scored_fb_event
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
import zmq

DEFAULT_BOX_THICKNESS = 4
DEFAULT_BOX_EXPANSION = 0
CROP_IMAGE = False
# Whether to force image resizing to a (square) integer size (not recommended to change this)
# None means no resizing.
IMAGE_SIZE = None

from camera_traps_MD.run_detector import load_and_run_detector


PORT = os.environ.get('IMAGE_GENERATING_PLUGIN_PORT', 6000)
base_path = os.environ.get('IMAGE_PATH')
image_path_prefix = os.environ.get('IMAGE_PATH_PREFIX')


def get_socket():
    # create the zmq context object
    context = zmq.Context()
    return get_plugin_socket(context, PORT)  

def get_image_file_path(image_uuid, image_format):
   """
   Returns the path on the file system to an image with the given uuid and format.
   """
   return f"{base_path}/{image_path_prefix}/{image_uuid}.{image_format}"


def main():
    socket = get_socket()
    done = False
    total_messages = 1
    while not done:
        # get the next message
        print(f"waiting on message: {total_messages}")
        m = get_next_msg(socket)
        e = bytes_to_typed_event(m)

        print(f"just got message {total_messages}; contents: {m}")
        total_messages += 1
        # TODO: we could check if e is not an image_received event, skip it....
        
        # - find the image on the file system, (the image path)
        image_uuid = e.ImageUuid()
        image_format = e.ImageFormat()
        image_file_path = get_image_file_path(image_uuid, image_format)                
        # score the image
        # NOTE: we already have the run_detector.py file (https://github.com/microsoft/CameraTraps/blob/main/detection/run_detector.py)
        # in the image, and we just need to call load_and_run_detector(), which is defined in that same file, 
        # in the same way that it is called in the file
        results= load_and_run_detector(model_file="md_v5a.0.0.pt",
                                       image_file_names=[image_file_path],
                                       output_dir=f"{base_path}/{image_path_prefix}",
                                       render_confidence_threshold=0.1,
                                       box_thickness=DEFAULT_BOX_THICKNESS,
                                       box_expansion=DEFAULT_BOX_EXPANSION,                          
                                       crop_images=CROP_IMAGE,
                                       image_size=IMAGE_SIZE)
        # create and send an image scored event with the probability scores:
        scores = []
        for r in results:
           # Each score object should have the format: 
           #     {"image_uuid": image_uuid, "label": "animal", "probability": 0.85}
           # Each result returned from detector is a dictionary with `category` and `conf`
           label = "unknown"
           if r['category'] == '1':
              label = "animal"
           elif r['category'] == '2':
              label = "human"
           elif r['category'] == '3':
              label = "transport vehicle"
           scores.append({"image_uuid": image_uuid, "label": label, "probability": r['conf']})
        print(f"Sending image scored event with the following scores: {scores}")
        send_image_scored_fb_event(socket, image_uuid, scores)
        

        if total_messages == 11:
            done = True




f = open('/example_images/detections.json')

data = json.load(f)
for i in data['images'] :
  for j in i['detections']:
    if(j['category']=="1" and i['max_detection_conf']==j['conf']):
      print(i["file"],j['conf'])


f.close()

if __name__ == "__main__":
   main()