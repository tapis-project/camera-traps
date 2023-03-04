import json
import os
import glob
import uuid
from collections import OrderedDict
import zmq
from PIL import Image
import ctevents
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command


# get the port assigned to the Image Generating plugin
PORT = os.environ.get('IMAGE_GENERATING_PLUGIN_PORT', 6000)


def get_socket():
    # create the zmq context object
    context = zmq.Context()
    return get_plugin_socket(context, PORT)


with open('input.json') as f:
    data = json.load(f)
user_input = data['path']
print(f"user_input: {user_input}")
start = int(data['timestamp'])


def get_binary(value):
    uuid_image = str(uuid.uuid5(uuid.NAMESPACE_URL, value))
    with open(str(value)[1:-1], "rb") as f:
        binary_img = f.read()
    img = Image.open(str(value)[1:-1])
    img_format = img.format
    ctevents.send_new_image_fb_event(
        socket, uuid_image, img_format, binary_img)


def simpleNext(i, value_index):
    if i >= len(img_dict):
        exit()
    value = list(img_dict.values())[i]
    val_Length = len(value)
    if (val_Length == 1):
        value = str(value)[1:-1]
        # UUID5 - SHA-1 hash [namestring is URL: https://docs.python.org/3/library/uuid.html]
        get_binary(value)
        return i + 1, value_index
    else:
        value = list(img_dict.values())[i][value_index]
        get_binary(value)
        if (value_index == val_Length - 1):
            return i + 1, 0
        return i, value_index + 1


def burstNext(index):
    burst_Quantity = int(data['burstQuantity'])
    for i in range(index, index+burst_Quantity):
        if (i >= len(img_dict)):
            exit()
        value = list(img_dict.values())[i]
        value = str(value)[1:-1]
        get_binary(value)
    return (index+burst_Quantity)


def identicalTimestamp(timestamp_min):
    if timestamp_min not in img_dict.keys():
        exit()
    if (len(img_dict[timestamp_min]) > 1):
        for i in range(0, len(img_dict[timestamp_min])):
            value = img_dict[timestamp_min][i]
            get_binary(value)
    return timestamp_min+start


def nextImage(timestamp_min, index):
    if index >= len(img_dict) or timestamp_min > timestamp_max:
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


def main():
    timestamp_min = list(img_dict.keys())[0]
    initial_index = 0
    index = 0
    indexvalue = 0

    done = False
    # while not done:
    for i in range(0, 15):
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
            print("Simple Next")
            index, indexvalue = simpleNext(index, indexvalue)


if __name__ == '__main__':
    main()
