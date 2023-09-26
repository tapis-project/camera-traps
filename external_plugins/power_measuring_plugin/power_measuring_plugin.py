# docker build --build-arg REL=latest -t test_power .
# docker run -it test_power:latest
# docker cp bold_herschel:/ /home/murphie/Project/cameraTrap/inspect_power
# docker build -t power_measuring_plugin .
from ctevents.ctevents import socket_message_to_typed_event, send_monitor_power_start_fb_event
from ctevents import MonitorPowerStartEvent, MonitorPowerStopEvent
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command

import os
import zmq
import json
import time
import queue
import logging
import datetime
import threading
import subprocess
from copy import deepcopy

logger = logging.getLogger("Power measurement")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

PORT = os.environ.get('POWER_MEASURING_PLUGIN_PORT', 6010)
LOG_DIR = os.environ.get('TRAPS_POWER_LOG_PATH', "/logs/")

TEST_FUNCTION = int(os.environ.get('TRAPS_TEST_POWER_FUNCTION', '0'))
stop = False
request_queue = queue.Queue()
DEVICE_TYPES_METHODS = {"cpu": {"scaph": "scaphandre stdout -t "}, "gpu": {"nvsmi": "nvidia-smi --query-gpu=index,power.draw --format=csv"}}


def get_log_file_location(file_name):
    """
    Return the absolute path to the log file location for a specific log file.
    file_name (str) should be the name of the file; i.e., "cpu.json", "gpu.json". etc. 
    """
    return os.path.join(LOG_DIR, file_name)

def run_cpu_measure(pids, duration, cpu_method):
    method = DEVICE_TYPES_METHODS["cpu"][cpu_method]
    cmd = method + str(duration)
    logger.info("start measuring PID={} CPU for {}s using {}".format(pids, duration, cpu_method))

    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    meta_infos = {}
    while not stop:
        output = process.stdout.readline()
        
        if output == "" and process.poll() is not None:
            break
        if output:
            for line in output.strip().splitlines():
                if line[-1] != '"':
                    continue

                current_time = datetime.datetime.now()
                readable_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                for pid in pids:
                    if str(pid) in line:
                        # logger.info(line)
                        meta_info = line.split('\t')
                        meta_info[0] = float(meta_info[0][:-2])
                        meta_info[1] = meta_info[1]
                        meta_info[2] = meta_info[2].strip('"')
                        meta_infos[readable_time] = meta_info
                        break
                    
        if len(meta_infos):
            with open(get_log_file_location('cpu.json'), 'w') as json_file:
                json.dump(meta_infos, json_file)
        


def run_gpu_measure(pids, duration, gpu_method):
    method = DEVICE_TYPES_METHODS["gpu"][gpu_method]
    cmd = method
    logger.info("start measuring PID={} GPU for {}s using {}".format(pids, duration, gpu_method))
    time_interval = 2

    meta_infos = {}
    while not stop and duration > 0:
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        while not stop:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                for line in output.strip().splitlines():
                    if line[-1] != 'W':
                        continue
                    current_time = datetime.datetime.now()
                    readable_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
                    meta_infos[readable_time] = float(line.split()[-2])
            with open(get_log_file_location('gpu.json'), 'w') as json_file:
                json.dump(meta_infos, json_file)

        process.wait()
        time.sleep(time_interval)
        duration -= time_interval


def run_power_measure(request_info, cpu_method="scaph", gpu_method="nvsmi"):

    logger.info(request_info)
    pids, devices, time_to_start, duration = request_info

    measure_cpu = False
    measure_gpu = False
    if 0 in devices:
        measure_cpu = True
        measure_gpu = True

    if 1 in devices:
        # cpu
        measure_cpu = True

    if 2 in devices:
        # gpu
        measure_gpu = True

    if(measure_cpu):
        cpu_thread = threading.Thread(target=run_cpu_measure, args=(pids, duration, cpu_method))
        cpu_thread.start()
    if(measure_gpu):
        gpu_thread = threading.Thread(target=run_gpu_measure, args=(pids, duration, gpu_method))
        gpu_thread.start()
        
    if(measure_cpu):
        cpu_thread.join()
    if(measure_gpu):
        gpu_thread.join()


def watcher():
    while not stop:
        if not request_queue.empty():
            task = request_queue.get()
            t = threading.Thread(target=run_power_measure, args=(task,))
            t.start()

def get_socket():
    """
    This function creates the zmq socket object and generates the event-engine plugin socket
    for the port configured for this plugin.
    """

    return get_plugin_socket(zmq.Context(), PORT)

def run():
    global stop
    logger.info("Start running ...")
    
    watcher_thread = threading.Thread(target=watcher, args=())
    watcher_thread.start()

    socket = get_socket()

    if TEST_FUNCTION == 1:
        logger.info("Debuging mode ...")
        my_pids = [os.getpid()]
        monitor_type = [0]
        monitor_duration = 10
        send_monitor_power_start_fb_event(socket, my_pids, monitor_type, monitor_duration)

    while not stop:
        message = get_next_msg(socket)
        event = socket_message_to_typed_event(message)
        if isinstance(event, MonitorPowerStartEvent):
            pids = event.PidsAsNumpy()
            types = event.MonitorTypesAsNumpy()
            start_time = event.MonitorStartTs()
            duration = event.MonitorSeconds()
            task = [pids, types, start_time, duration]
            request_queue.put(deepcopy(task))
            logger.info("Got a power monitor event...")
        elif isinstance(event, MonitorPowerStopEvent):
            stop = True


if __name__ == "__main__":
    run()