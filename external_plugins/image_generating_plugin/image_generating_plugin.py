import json, csv
import os
import glob
import uuid
from collections import OrderedDict
import zmq
import time
from PIL import Image
import threading
import concurrent.futures
from ctevents import ctevents
from ctevents.ctevents import send_terminating_plugin_fb_event
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
import requests
import zipfile
from io import BytesIO
import logging

log_level = os.environ.get("IMAGE_GENERATING_LOG_LEVEL", "INFO")
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
    Loads ground truth data from ground_truth.csv and add it as a dictionary.
    Returns:
        dict: A dictionary where the keys are image names and the values are the corresponding ground truth data.
    """
    config_dir = os.environ.get("CAMERA_TRAPS_DIR", '')
    ground_truth_file = os.path.join(config_dir, 'ground_truth.csv')
    ground_truth_data = {}
    try:
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

def oracle_monitoring_info(track_image_count, uuid, uuid_image):
    """
    Creates a file named image_mapping.json that stores information about the image file.
    Args:
        track_image_count (int): The count of image.
        uuid (str): The unique identifier for the image.
        uuid_image (str): The original name of the image file.
        ground_truth(global dictionary): Contains ground truth information for the object in the image.
    """
    OUTPUT_DIR = os.environ.get('TRAPS_MAPPING_OUTPUT_PATH', "/output/")
    file_name = "image_mapping.json"
    output_file = os.path.join(OUTPUT_DIR, file_name)
    ground_truth_info = ground_truth.get(uuid_image, 'unavailable')
    new_data = {
        "image_count": track_image_count,
        "UUID": uuid,
        "image_name": uuid_image,
        "ground_truth": ground_truth_info,
    }
    mapping = {}
    if os.path.exists(output_file):
        with open(output_file, 'r') as file:
            try:
                mapping = json.load(file)
            except json.JSONDecodeError as e:
                logger.error("Failed to decode JSON, exception:", e)
    mapping.setdefault(uuid,[]).append(new_data)
    with open(output_file, 'w') as file:
        json.dump(mapping, file, indent=2)

def get_binary(value, track_image_count, socket):
    """
    This function is used to generate the uuid, image format and binary image and invokes the  
    new image event.
    """
    uuid_image = str(uuid.uuid5(uuid.NAMESPACE_URL, value))
    with open(value, "rb") as f:
        binary_img = f.read()
    img = Image.open(value)
    img_format = img.format
    logger.info(f"sending new image with the following data: image:{value}; uuid:{uuid_image}; format: {img_format}; type(format): {type(img_format)}")
    try: 
        oracle_monitoring_info(track_image_count,uuid_image,value)
        ctevents.send_new_image_fb_event(socket, uuid_image, img_format, binary_img)     
    except Exception as e:
        logger.error(f"got exception {e}")

def monitor_generating_power(socket):
    monitor_flag = os.getenv('MONITOR_POWER')
    pid = [os.getpid()]
    monitor_type = [1]
    monitor_seconds = 0
    if monitor_flag:
        ctevents.send_monitor_power_start_fb_event(socket, pid, monitor_type, monitor_seconds)
        logger.info(f"Monitoring image generating power")

def simpleNext(img_dict, i, value_index, track_image_count, socket):
    """
    This function is used to retrieve the next image specified in the directory based on the timestamp
    and invokes get binary function.
    """
    done = False
    if i >= len(img_dict):
        done = True
        logger.info(f"Hit exit condition; i: {i}; len(img_dict): {len(img_dict)}; done = {done}")
        return done, i, len(img_dict)
    value = list(img_dict.values())[i][value_index]
    get_binary(value, track_image_count,socket)
    # if we hit the end of the current list, move to the next time stamp
    if value_index == len(list(img_dict.values())[i]) - 1:
        return done, i+1, 0
    print(f"returning simpleNext: {done}, {i}, {value_index + 1}")
    return done, i, value_index + 1


def burstNext(img_dict,index,socket):
    """
    This function send the next x (burstQuantity specified) images specified in the directory based on the timestamp
    and invokes get binary function. 
    """
    # TODO -- burstNext currently produces the same behavior as simpleNext. We 
    #         should think through how to achieve burst behavior in a simulation.
    burst_Quantity = int(data['burstQuantity'])
    for i in range(index, index+burst_Quantity):
        if (i >= len(img_dict)):
            done = True
            print(f"Hit exit condition; i: {i}; len(img_dict): {len(img_dict)}; done = {done}")
            return done, i, len(img_dict)
        value = list(img_dict.values())[i]
        value = str(value)[1:-1]
        get_binary(value,socket)
    return (index+burst_Quantity)


def identicalTimestamp(img_dict, timestamp_min,socket):
    """
    Incase of multiple images with same timestamp, this function gets single image
    and invokes get binary function.
    """
    # NEEDS IMG_DICT AND START
    if timestamp_min not in img_dict.keys():
        print(f"Hit exit condition...timestamp_min not in img_dict.keys()")
        exit()
    if (len(img_dict[timestamp_min]) > 1):
        for i in range(0, len(img_dict[timestamp_min])):
            value = img_dict[timestamp_min][i]
            get_binary(value,socket)
    return timestamp_min+start


def nextImage(img_dict,timestamp_min, index,socket):
    """
    For a given static time interval(t), this fucntion gives the next image t seconds forward.
    Binary search algorithm is used to minimize the search time.
    """
    # TODO -- currently, the nextImage function depends on OS timestamps on the input images, 
    #         and therefore may not function/may give unexpected results. 
    # NEEDS IMG_DICT AND START AND  TIMESTAMP_MAX
    if index >= len(img_dict):
        print(f"Hitting exit condition; index: {index}; len(image_dict): {len(img_dict)}")
        
        exit()
    if timestamp_min > timestamp_max:
        print(f"Hitting exit condition; timestamp_min: {timestamp_min}; timestamp_max: {timestamp_max}")
        exit()
    start1 = index
    end = len(img_dict)-1
    while start1 <= end:
        mid = (start1 + end) // 2
        mid_value = list(img_dict.keys())[mid]
        if mid_value < timestamp_min:
            start1 = mid + 1
        else:
            index = mid
            end = mid - 1
    timestamp_min1 = list(img_dict.keys())[index]
    value = img_dict[timestamp_min1]
    value = str(value)[1:-1]
    get_binary(value, socket)
    return timestamp_min1+start, index


def randomImage(timestamp_min, index, socket):
    """
    For a given dynamic time interval(t), this fucntion gives the next image t seconds forward.
    Binary search algorithm is used to minimize the search time.
    """
    if index >= len(img_dict) or timestamp_min > timestamp_max:
        exit()
    start1 = index
    print(timestamp_min)
    end = len(img_dict)-1
    while start1 <= end:
        mid = (start1 + end) // 2
        mid_value = list(img_dict.keys())[mid]
        if mid_value < timestamp_min:
            start1 = mid + 1
        else:
            index = mid
            end = mid - 1
    timestamp_min = list(img_dict.keys())[index]
    value = img_dict[timestamp_min]
    value = str(value)[1:-1]
    get_binary(value,socket)
    return timestamp_min, index

def extract_from_zipfile(url, socket):
    """
    This function helps to extract images from input url.
    """
    response = requests.get(url)
    if response.status_code == 200:
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zip_ref:
            file_list = zip_ref.namelist()
            for file_name in file_list:
                if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    with zip_ref.open(file_name) as image_file:
                        uuid_image = str(uuid.uuid5(uuid.NAMESPACE_URL, file_name))
                        binary_img = image_file.read()
                        img = Image.open(BytesIO(binary_img))
                        img_format = img.format
                        logger.info(f"sending new image with the following data: image:{file_name}; uuid:{uuid_image}; format: {img_format}; type(format): {type(img_format)}")
                        try:
                            ctevents.send_new_image_fb_event(socket, uuid_image, img_format, binary_img)
                        except Exception as e:
                            logger.error(f"got exception {e}")
        logger.info(f"Successfully extracted images from the url - {url}")
    else:
        logger.error(f"Failed to download file from {url}")
    
def get_config():
    # TODO - return start
    # get the configuration file location
    config_dir = os.environ.get("CAMERA_TRAPS_DIR", '')
    config_file = os.path.join(config_dir, 'input.json')

    logger.info("Image Generating Plugin starting up...")
    with open(config_file) as f:
        data = json.load(f)
    user_input = data['path']
    logger.info(f"user_input: {user_input}")
    start = int(data['timestamp']) # used for nextImage and identicalTimestamp
    return data

def create_dict(data):
    """
    Creates an ordered dictionary with the image files in the directory.
    Future: Think of a way to minimize the memory usage
    """
    user_input = data['path']
    list_of_files = filter(os.path.isfile, glob.glob(user_input + '/*'))
    list_of_files = sorted(list_of_files, key=os.path.getmtime)
    length_of_files = len(list_of_files)
    #logging.trace(f"list_of_files: {list_of_files}")
    img_dict = OrderedDict()
    for file_name_full in list_of_files:
        if ('.DS_Store' not in file_name_full):
            timestamp = int(os.path.getmtime(file_name_full))
            if timestamp in img_dict.keys():
                img_dict[timestamp] += [file_name_full]
            else:
                img_dict[timestamp] = [file_name_full]
    timestamp_max = list(img_dict.keys())[len(img_dict) - 1]
    timestamp_min = list(img_dict.keys())[0]

    return img_dict, timestamp_min, timestamp_max, list_of_files

def send_images(data, socket):
    """
    send a new image until out of images, checks for quit message
    """
    done = False
    index = 0
    index_value = 0
    initial_index = 0
    track_image_count = 1
    print(data['path'])
    if data['path'].endswith(('.zip', '.rar')):
        extract_from_zipfile(data['path'], socket)
        
    img_dict, timestamp_min, timestamp_max,list_of_files = create_dict(data)
    length_of_files = len(list_of_files)

    while not done:
        print("\n* * * * * * * * * * ")
        logger.info(f"Processing file {track_image_count} of {length_of_files}")
        logger.debug(f"Top of send_images loop; index: {index}; index_value: {index_value}; initial_index: {initial_index}")
        done, index, index_value = send_new_image(data, index, index_value, initial_index, track_image_count, socket)
        logger.debug(f"Bottom of send_images loop; index: {index}; index_value: {index_value}; initial_index: {initial_index}")
        print("* * * * * * * * * * \n")
        # try:
        #     msg = get_next_msg(socket, timeout=10)
        #     if msg == "PluginTerminateEvent":
        #         send_quit_command(socket)
        # except zmq.error.Again:
        #     continue
        track_image_count+=1
    print("Bottom of send_images; exiting...")
    send_terminating_plugin_fb_event(socket,"ext_image_gen_plugin","d3266646-41ec-11ed-a96f-5391348bab46")
    logger.debug(f"list_of_files: {list_of_files}")


def send_new_image(data, index, indexvalue, inital_index,track_image_count, socket):
    img_dict, timestamp_min, timestamp_max, list_of_files = create_dict(data)

    if data['callingFunction'] == "nextImage":
        print("Timed Next")
        timestamp_min, initial_index = nextImage(
            img_dict,timestamp_min, initial_index, socket)
    elif data['callingFunction'] == "burstNext":
        print("Burst Next")
        index = burstNext(img_dict,index, socket)
    elif data['callingFunction'] == "identicalTimestamp":
        print("Identical Timestamp")
        timestamp_min = identicalTimestamp(img_dict, timestamp_min, socket)
        print(timestamp_min)
    elif data['callingFunction'] == "randomImage":
        print("Random Image")
        random_timestamp = int(
            input("Enter the random timestamp in seconds: "))
        timestamp_min += random_timestamp
        timestamp_min, initial_index = randomImage(
            img_dict, timestamp_min, initial_index,socket)
    else:
        print(f"Calling simpleNext with: {index}, {indexvalue}")
        return simpleNext(img_dict, index, indexvalue,track_image_count, socket)
        
def check_quit(socket):
    done = False
    while not done:
        try:
            get_next_msg(socket)
        except:
            print("check quit exception")
            time.sleep(5)

def main():
    socket = get_socket()
    data = get_config()
    global ground_truth
    ground_truth = load_ground_truth()
    monitor_generating_power(socket)
    send_images(data, socket)
    
    # with concurrent.futures.ThreadPoolExecutor() as executor:
    #     # run send_new_image and get_next_msg concurrently
    #     thread1 = executor.submit(send_images, data, socket)
    #     thread2 = executor.submit(check_quit, socket)  
        
    #     message = thread2.result()

    #     if message == "PluginTerminateEvent":
    #         send_quit_command(socket)



if __name__ == '__main__':
    logger.info("Image generating plugin starting...")
    main()
    # sleep a few seconds before exiting to allow power plugin to look up our PID 
    time.sleep(5)
    logger.info("Image generating plugin exiting...")
