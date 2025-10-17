from io import BytesIO
import logging
import os
from PIL import Image
import time
import uuid 
import zmq 
import yaml
import logging
import subprocess
import sys

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ctevents import ctevents
from pyevents.events import get_plugin_socket, send_quit_command
from ctevents.ctevents import send_terminate_plugin_fb_event

# Path to a directory that this plugin "watches" for new image files. 
# By default, we set this directory to `/var/lib/motion` in the container, assuming
# that the Linux Motion package will also be configured and running in the same container.
log_level = os.environ.get("IMAGE_GENERATING_LOG_LEVEL", "INFO")
DATA_MONITORING_PATH = os.environ.get("DATA_MONITORING_PATH", "/var/lib/motion")
MIN_SECONDS_BETWEEN_IMAGES = float(os.environ.get("MIN_SECONDS_BETWEEN_IMAGES", "2.0"))
MODE = os.environ.get("MODE", "demo")
DEVICE=os.environ.get("DEVICE")

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
                if 'device_capability' in line:
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
    if MODE == 'simulation':
        video_info_file = os.environ.get('TRAPS_VIDEO_INFO_PATH', '/video_info.yaml')

        while not os.path.exists(video_info_file):
            time.sleep(1)

        try:
            with open(video_info_file, 'r') as f:
                video_info = yaml.safe_load(f)
        except Exception as e:
            logging.error(f'Error processing {video_info_file}: {e}')

        if 'duration' not in video_info.keys():
            logging.error(f'duration value not set in {video_info_file}')
        else:
            return video_info['duration']

def test_camera(v4l2_device=None):
    if v4l2_device:
        sample_img = '/tmp/sample.png'
        try:
            result = subprocess.run(
                ['ffmpeg', '-f', 'v4l2', '-i', v4l2_device, '-frames', '1', sample_img],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            logging.info(f'Captured sample image')
        except subprocess.CalledProcessError as e:
            global socket
            logging.error(f'Error: Failed to capture image from {v4l2_device}. {e.stderr.decode()}')
            logger.info('Sending quit command')
            send_terminate_plugin_fb_event(socket, "*", "35f20cdd-a404-4436-8df9-d80a9de91147")
            send_quit_command(socket)
            sys.exit()


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

    # Check camera before starting motion
    #test_camera(v4l2_device=DEVICE)

    # Startup motion
    duration = get_duration()
    motion_proc = subprocess.Popen(['motion'])

    # make sure motion is connected to camera
    log_observer = Observer()
    log_handler = LogFileHandler(log_observer, '/var/log/motion/motion.log')
    log_observer.schedule(log_handler, '/var/log/motion', recursive=False)
    log_observer.start()
    log_observer.join()
    logger.info('motion has connected to camera')
    with open('/tmp/ready', 'w') as f:
        f.write('Application is ready\n')
    
    # instantiate and start the event handler 
    event_handler = NewFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()

    # run for specified video duration, or if undefined until interrupted 
    try:
        if duration:
            logger.info(f'Running motion for {duration} seconds')
            time.sleep(duration)
            observer.stop()
        else:
            logger.info('No duration specified. Running motion indefinitely')
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    motion_proc.kill()
    logger.info('Sending quit command')
    send_terminate_plugin_fb_event(socket, "*", "35f20cdd-a404-4436-8df9-d80a9de91147")
    send_quit_command(socket)
