from io import BytesIO
import logging
import os
from PIL import Image
import time
import uuid 
import zmq 

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ctevents import ctevents
from pyevents.events import get_plugin_socket

# Path to a directory that this plugin "watches" for new image files. 
# By default, we set this directory to `/var/lib/motion` in the container, assuming
# that the Linux Motion package will also be configured and running in the same container.
DATA_MONITORING_PATH = os.environ.get("DATA_MONITORING_PATH", "/var/lib/motion")


def get_socket():
    """
    This function creates the zmq socket object and generates the event-engine plugin socket
    for the port configured for this plugin.
    """
    # get the port assigned to the Image Generating plugin
    PORT = os.environ.get('IMAGE_DETECTING_PLUGIN_PORT', 6000)
    # create the zmq context object
    context = zmq.Context()
    socket = get_plugin_socket(context, PORT)
    socket.RCVTIMEO = 100 # in milliseconds
    return socket


def generate_new_image_event(file_path):
    """
    Generates a new image event for a given file path.
    """
    if not file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        # we only generate events for image files in extensions that we recognize
        logging.info(f"Skipping non-image file at path: {file_path}")
        return None 
    
    # get the binary contents of the image to send in the message
    try:
        with open(file_path, 'rb') as f:
            binary_img = f.read()
    except Exception as e:
        logging.error(f"Got exception trying to read the file path ({file_path}); e: {e}")
        return None 
    
    # use PIL to get the image format 
    try:
        img = Image.open(file_path)
    except Exception as e:
        logging.error(f"Got exception trying to open file path ({file_path}) with PIL; e: {e}")
        return None 
    img_format = img.format

    # generate an image UUID
    image_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, file_path))
    
    # send a new image event 
    logging.info(f"Sending new image event with the following data: \
                image:{file_path}; uuid:{image_uuid}; format: {img_format}")
    
    try:
        ctevents.send_new_image_fb_event(socket, image_uuid, img_format, binary_img)
    except Exception as e: 
        logging.error(f"Got exception trying to send new image event for uuid: {image_uuid}; e: {e}")
        return None 
    
    # return the UUID
    return image_uuid


class NewFileHandler(FileSystemEventHandler):
    """
    Basic watchdog class to detect new files in the configured directory. 
    For now, we are only interested in *new* files, hence, we implement
    on_create.
    """
    def on_closed(self, event):
        """
        Watch the directory for new files (not directories), and trigger the 
        process_file function on such events. 
        """
        if not event.is_directory:
            file_path = event.src_path
            logging.info(f"New file detected: {file_path}")
            self.process_file(file_path)

    def process_file(self, file_path):
        """
        Basic processing of a new file event. 
        """
        try:
            logging.debug(f"Processing file at path: {file_path}")
            uuid = generate_new_image_event(file_path)
            logging.info(f"Generated uuid ({uuid}) and successfully sent new image event for file: {file_path}")
        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    path = DATA_MONITORING_PATH 
    
    # create a global instance of the zmq socket so that it is available within
    # the watchdog methods
    global socket
    socket = get_socket()
    logging.info(f"Image Detecting Plugin starting, monitoring path: {path}")
    
    # instantiate and start the event handler 
    event_handler = NewFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()

    # run until interrupted 
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
