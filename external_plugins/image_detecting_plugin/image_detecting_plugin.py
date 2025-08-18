from io import BytesIO
import logging
import os
from PIL import Image
import time
import uuid 
import zmq 
from subprocess import Popen

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ctevents import ctevents
from pyevents.events import get_plugin_socket

# Path to a directory that this plugin "watches" for new image files. 
# By default, we set this directory to `/var/lib/motion` in the container, assuming
# that the Linux Motion package will also be configured and running in the same container.
DATA_MONITORING_PATH = os.environ.get("DATA_MONITORING_PATH", "/var/lib/motion")
MIN_SECONDS_BETWEEN_IMAGES = float(os.environ.get("MIN_SECONDS_BETWEEN_IMAGES", "2.0"))
MODE = os.environ.get("MODE", "demo")

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

class LogFileHandler(FileSystemEventHandler):
    """
    watchdog class to detect updates to the motion.log file and notify when it
    has connected to a camera.
    """
    def __init__(self, observer, log_file_path):
        super().__init__()
        self.log_file_path = log_file_path
        self.observer = observer
        self.last_pos = 0

    def on_modified(self, event):
        if event.src_path == self.log_file_path:
            self.check_for_connection()

    def check_for_connection(self):
        with open(self.log_file_path, 'r') as f:
            f.seek(self.last_pos)
            new_lines = f.readlines()
            self.last_pos = f.tell()

            for line in new_lines:
                if 'motion detection Enabled' in line:
                    self.observer.stop()
                    return

class NewFileHandler(FileSystemEventHandler):
    """
    Basic watchdog class to detect new files in the configured directory. 
    For now, we are only interested in *new* files, hence, we implement
    on_create.
    """

    def __init__(self):
        super().__init__()
        self.last_image_time = 0

    def extract_timestamp(self, file_path):
        basename = os.path.basename(file_path)
        try:
            # Expected format: 20250714-21:51:49-00.jpg
            if "-" in basename and ":" in basename:
                # Splitting logic
                parts = basename.split("-")
                if len(parts) >= 2 and ":" in parts[1]:
                    date_part = parts[0]
                    time_part = parts[1].replace(":", "")
                    datetime_str = date_part + time_part
                    if len(datetime_str) == 14:
                        ts = time.strptime(datetime_str, "%Y%m%d%H%M%S")
                        return time.mktime(ts)
        except Exception as e:
            logging.warning(f"Filename parsing failed: {basename} — {e}")

        # Fallback
        try:
            return os.path.getmtime(file_path)
        except Exception as e:
            logging.warning(f"Fallback to time.time(): {file_path} — {e}")
            return time.time()
        
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
            current_time = self.extract_timestamp(file_path)
            if current_time - self.last_image_time < MIN_SECONDS_BETWEEN_IMAGES:
                logging.info(f"Skipping image (too soon): {file_path}") 
                os.remove(file_path)
                return

            logging.debug(f"Processing file at path: {file_path}")
            uuid = generate_new_image_event(file_path)
            if uuid:
                self.last_image_time = current_time
                logging.info(f"Generated uuid ({uuid}) and successfully sent new image event for file: {file_path}")
        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")

def get_duration():
    if MODE == 'video_simuation':
        video_info_file = os.environ.get('TRAPS_VIDEO_INFO_PATH', '/video_info/video_info.yaml')
        while True:
            if os.path.exists(video_info_file):
                try:
                    with open(video_info_file, 'r') as f:
                        video_info = yaml.safe_load(f)
                except Exception as e:
                    logging.error(f'Error processing {video_info_file}: {e}')
            else:
                sleep(1)

        if 'duration' not in video_info.keys():
            logging.error(f'duration value not set in {video_info_file}')
        else:
            duration = video_info['duration']


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

    # Startup motion
    duration = get_duration()
    motion_proc = Popen(['motion'])

    # make sure motion is connected to camera
    log_observer = Observer()
    log_handler = LogFileHandler(log_observer, '/var/log/motion/motion.log')
    log_observer.schedule(log_handler, '/var/log/motion', recursive=False)
    log_observer.start()
    
    # instantiate and start the event handler 
    event_handler = NewFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()

    # run for specified video duration, or if undefined until interrupted 
    try:
        if duration:
            time.sleep(duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    motion_proc.kill()
