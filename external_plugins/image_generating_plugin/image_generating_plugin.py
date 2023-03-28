import json
import os
import glob
import uuid
from collections import OrderedDict
import zmq
from PIL import Image
from ctevents import ctevents
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command


# get the port assigned to the Image Generating plugin
PORT = os.environ.get('IMAGE_GENERATING_PLUGIN_PORT', 6000)


def get_socket():
    """
    This function creates the zmq socket object and generates the event-engine plugin socket
    for the port configured for this plugin.
    """
    # create the zmq context object
    context = zmq.Context()
    return get_plugin_socket(context, PORT)


def get_binary(value):
    """
    This function is used to generate the uuid, image format and binary image and invokes the  
    new image event.
    """
    uuid_image = str(uuid.uuid5(uuid.NAMESPACE_URL, value))
    with open(value, "rb") as f:
        binary_img = f.read()
    img = Image.open(value)
    img_format = img.format
    print(f"sending new image with the following data; uuid:{uuid_image}; format: {img_format}; type(format): {type(img_format)}")
    ctevents.send_new_image_fb_event(
        socket, uuid_image, img_format, binary_img)


def simpleNext(i, value_index):
    """
    This function is used to retrieve the next image specified in the directory based on the timestamp
    and invokes get binary function.
    """
    if i >= len(img_dict):
        done = True
        print(f"Hit exit condition; i: {i}; len(img_dict): {len(img_dict)}; done = {done}")
        exit()
    value = list(img_dict.values())[i][value_index]
    get_binary(value)
    # if we hit the end of the current list, move to the next time stamp
    if value_index == len(list(img_dict.values())[i]) - 1:
        return i+1, 0
    return i, value_index + 1


def burstNext(index):
    """
    This function send the next x (burstQuantity specified) images specified in the directory based on the timestamp
    and invokes get binary function. 
    """
    # TODO -- burstNext currently produces the same behavior as simpleNext. We 
    #         should think through how to achieve burst behavior in a simulation.
    burst_Quantity = int(data['burstQuantity'])
    for i in range(index, index+burst_Quantity):
        if (i >= len(img_dict)):
            exit()
        value = list(img_dict.values())[i]
        value = str(value)[1:-1]
        get_binary(value)
    return (index+burst_Quantity)


def identicalTimestamp(timestamp_min):
    """
    Incase of multiple images with same timestamp, this function gets single image
    and invokes get binary function.
    """
    if timestamp_min not in img_dict.keys():
        print(f"Hit exit condition...timestamp_min not in img_dict.keys()")
        exit()
    if (len(img_dict[timestamp_min]) > 1):
        for i in range(0, len(img_dict[timestamp_min])):
            value = img_dict[timestamp_min][i]
            get_binary(value)
    return timestamp_min+start


def nextImage(timestamp_min, index):
    """
    For a given static time interval(t), this fucntion gives the next image t seconds forward.
    Binary search algorithm is used to minimize the search time.
    """
    # TODO -- currently, the nextImage function depends on OS timestamps on the input images, 
    #         and therefore may not function/may give unexpected results. 
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
    print("Output")
    value = img_dict[timestamp_min1]
    value = str(value)[1:-1]
    get_binary(value)
    return timestamp_min1+start, index


def randomImage(timestamp_min, index):
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
    print("Output")
    value = img_dict[timestamp_min]
    value = str(value)[1:-1]
    get_binary(value)
    return timestamp_min, index


print("Image Generating Plugin starting up...")
with open('input.json') as f:
    data = json.load(f)
user_input = data['path']
print(f"user_input: {user_input}")
start = int(data['timestamp'])
"""
Creates an ordered dictionary with the image files in the directory.
Future: Think of a way to minimize the memory usage
"""

list_of_files = filter(os.path.isfile, glob.glob(user_input + '/*'))
list_of_files = sorted(list_of_files, key=os.path.getmtime)
print(f"list_of_files: {list_of_files}")
img_dict = OrderedDict()
for file_name_full in list_of_files:
    if ('.DS_Store' not in file_name_full):
        timestamp = int(os.path.getmtime(file_name_full))
        if timestamp in img_dict.keys():
            img_dict[timestamp] += [file_name_full]
        else:
            img_dict[timestamp] = [file_name_full]
timestamp_max = list(img_dict.keys())[len(img_dict) - 1]
socket = get_socket()
done = False

def main():
    timestamp_min = list(img_dict.keys())[0]
    initial_index = 0
    index = 0
    indexvalue = 0

    
    while not done:
    #for i in range(0, 100):
        if data['callingFunction'] == "nextImage":
            print("Timed Next")
            timestamp_min, initial_index = nextImage(
                timestamp_min, initial_index)
        elif data['callingFunction'] == "burstNext":
            print("Burst Next")
            index = burstNext(index)
        elif data['callingFunction'] == "identicalTimestamp":
            timestamp_min = identicalTimestamp(timestamp_min)
            print(timestamp_min)
        elif data['callingFunction'] == "randomImage":
            random_timestamp = int(
                input("Enter the random timestamp in seconds: "))
            timestamp_min += random_timestamp
            timestamp_min, initial_index = randomImage(
                timestamp_min, initial_index)
        else:
            print(f"Simple Next; index: {index}; indexvalue: {indexvalue} ")
            index, indexvalue = simpleNext(index, indexvalue)


if __name__ == '__main__':
    main()
