import json, csv
import os
import glob
import uuid
import zmq
import time
from PIL import Image
from ctevents import ctevents
from ctevents.ctevents import send_terminating_plugin_fb_event
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
import requests
import zipfile
from io import BytesIO
import logging
from filelock import FileLock

log_level = os.environ.get("IMAGE_GENERATING_LOG_LEVEL", "INFO")
input_image_path = os.environ.get("INPUT_IMAGE_PATH", "/example_images")
use_ground_truth_url = os.environ.get("USE_CUSTOM_GROUND_TRUTH_FILE_URL", False)
ground_truth_url = os.environ.get("CUSTOM_GROUND_TRUTH_URL")
ground_truth_file = os.environ.get("GROUND_TRUTH_FILE", "/ground_truth_dir/ground_truth.csv")

# The model_variant is only used to specify the ID in the ground_truth file, so we use that environment 
# variable here. 
model_variant = os.environ.get('MODEL_ID', '0')

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
    PORT = os.environ.get('IMAGE_GENERATING_PLUGIN_PORT', 6000)
    # create the zmq context object
    context = zmq.Context()
    socket = get_plugin_socket(context, PORT)
    socket.RCVTIMEO = 100 # in milliseconds
    return socket

def load_ground_truth():
    """
    Parses through the input ground truth file and creates a dictionary {image_name:ground_truth}.
    Returns:
        dict: A dictionary where the keys are image names and the values are the corresponding ground truth data.
    """
    logger.info("Retrieving the ground truth file in image generating plugin")
    ground_truth_data = {}
    try:
        if use_ground_truth_url:
            logger.info(f"Retrieving custom ground truth file: {ground_truth_url}")
            response = requests.get(ground_truth_url)
            if response.status_code == 200:
                csv_content = response.content.decode('utf-8').splitlines()
                reader = csv.DictReader(csv_content)
                for row in reader:
                    image_name = row['image_name']
                    ground_truth_data[image_name] = row['ground_truth']
        else:
            with open(ground_truth_file, mode='r') as ground_truth:
                reader = csv.DictReader(ground_truth)
                for row in reader:
                    image_name = row['image_name']
                    ground_truth_data[image_name] = row['ground_truth']
    except FileNotFoundError:
        logger.error(f"File not found: {ground_truth_file}")
    except KeyError as e:
        logger.error(f"Missing expected column in CSV: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return ground_truth_data


def oracle_monitoring_info(track_image_count, image_uuid, image_name, ground_truth):
    """
    This function is called by get_binary for each image processed in the main loop.It 
    creates and/or updates the uuid_image_mapping.json file that stores information about the image file.
    
    Args:
        track_image_count (int): The count of image.
        uuid (str): The unique identifier for the image.
        uuid_image (str): The original name of the image file.
        ground_truth: Contains ground truth information for the object in the image.
    """
    logger.info("Creating mapping file in image generating plugin")
    OUTPUT_DIR = os.environ.get('TRAPS_MAPPING_OUTPUT_PATH', "/output/")

    # look up the image in the ground_truth dictionary
    ground_truth_info = ground_truth.get(image_name, 'unavailable')
    # A value of 'unavailable' is unexpected, as it means there is a missing entry in the dictionary, 
    # but we do not let that stop the entire program, we just log it as an error:
    if ground_truth_info == 'unavailable':
        logger.error(f"ERROR: Could not determine ground truth value for image {image_name}; no entry in ground_truth dict.")
    
    # build the mapping dictionary for this image
    image_mapping_dict = {
        "image_count": track_image_count,
        "UUID": image_uuid,
        "image_name": image_name,
        "ground_truth": ground_truth_info,
        "model_id": model_variant,
    }
    
    # Read the uuid image mapping file to build the current map:
    mapping = {}
    image_mapping_file = os.path.join(OUTPUT_DIR, "uuid_image_mapping.json")
    lock = FileLock(f'{image_mapping_file}.lock')
    with lock:
        if os.path.exists(image_mapping_file):
            with open(image_mapping_file, 'r') as file:
                try:
                    mapping = json.load(file)
                except json.JSONDecodeError as e:
                    logger.error("Failed to decode JSON, exception:", e)
   
        # Insert the new image into the map
        mapping[image_uuid] = image_mapping_dict
        
        # Write the updated map back to the file
        with open(image_mapping_file, 'w') as file:
            json.dump(mapping, file, indent=2)


def get_binary(file_name, binary_img, img_format, track_image_count, total_images, ground_truth):
    """
    This function is used to generate the uuid, image format and binary image and invokes the  
    new image event.
    """
    logger.info(f"Processing file {file_name} ({track_image_count} of {total_images})")
    image_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, file_name))
    logger.info(f"Sending new image with the following data: image:{file_name}; uuid:{image_uuid}; format: {img_format}; type(format): {type(img_format)}")
    try: 
        # first update the uuid_image_mapping.json file
        oracle_monitoring_info(track_image_count, image_uuid, file_name, ground_truth)
        
        # then send the new image event; this should ensure that the mapping file always contains the 
        # the image prior to a subsequent plugin processing it. 
        ctevents.send_new_image_fb_event(socket, image_uuid, img_format, binary_img)     
    except Exception as e:
        logger.error(f"ERROR: got exception {e}")
    if track_image_count>=total_images:
        logger.info(f"Succesfully processed {track_image_count} images and inititated terminating plugin from image generating plugin")
        send_terminating_plugin_fb_event(socket,"ext_image_gen_plugin","d3266646-41ec-11ed-a96f-5391348bab46")


def monitor_generating_power():
    """
    This function is used to initiate the power monitoring event, if the monitoring flag is set.
    """
    monitor_flag = os.getenv('MONITOR_POWER')
    pid = [os.getpid()]
    monitor_type = [1]
    monitor_seconds = 0
    if monitor_flag:
        ctevents.send_monitor_power_start_fb_event(socket, pid, monitor_type, monitor_seconds)
        logger.info(f"Monitoring image generating power")


def extract_from_zipfile(url, ground_truth):
    """
    This function helps to extract images from input url.
    """
    response = requests.get(url)
    if response.status_code == 200:
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zip_ref:
            file_list = zip_ref.namelist()
            track_image_count = 0
            total_images = len(file_list)
            for file_name in file_list:
                if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    with zip_ref.open(file_name) as image_file:
                        track_image_count+=1
                        binary_img = image_file.read()
                        img = Image.open(BytesIO(binary_img))
                        img_format = img.format
                        get_binary(file_name, binary_img, img_format, track_image_count, total_images, ground_truth)
        logger.info(f"Successfully extracted images from the url - {url}")
    else:
        logger.error(f"Failed to download file from {url}")


def process_images(input_image_path, ground_truth):
    """
    Main function that loops through the set of images and processes each one by ultimately sending a 
    new image event for each. The actual sending of the event happens in get_binary.
    """
    logger.info(f"The input image path specified by the user:{input_image_path}")
    if input_image_path.endswith(('.zip', '.rar')):
        extract_from_zipfile(input_image_path, ground_truth)
    else:
        track_image_count = 0
        # NOTE: this just counts the total number of files (not including subdirectories) in the path; later, we check for the
        #       file extension and only process supported types, so this could be an issue.
        total_images = len([name for name in os.listdir(input_image_path) if os.path.isfile(os.path.join(input_image_path, name))])
        
        # Iterate through the input image directory and process each file of a supported extension.
        for image_file in os.listdir(input_image_path):
            file_name = os.path.join(input_image_path, image_file)
            
            # check if the file is supported
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                track_image_count += 1
                # read the binary contents of the file and determine the format officially
                with open(file_name, "rb") as f:
                    binary_img = f.read()            
                img = Image.open(file_name)
                img_format = img.format
                # get_binary does the main processing for each image
                get_binary(file_name, binary_img, img_format, track_image_count, total_images, ground_truth)


def main():
    global socket
    socket = get_socket()
    ground_truth = load_ground_truth()
    monitor_generating_power()
    process_images(input_image_path, ground_truth)
    send_quit_command(socket)

if __name__ == '__main__':
    logger.info("Image generating plugin starting...")
    main()
    logger.info("Image generating plugin exiting...")
