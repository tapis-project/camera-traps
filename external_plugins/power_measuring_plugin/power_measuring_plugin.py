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
import jtop_backend
import scaphandre_backend


logger = logging.getLogger("Power measurement")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

PORT = os.environ.get('POWER_MEASURING_PLUGIN_PORT', 6010)
LOG_DIR = os.environ.get('TRAPS_POWER_LOG_PATH', "/logs/")

TEST_FUNCTION = int(os.environ.get('TRAPS_TEST_POWER_FUNCTION', '0'))
stop = False


# BACKEND could be jtop or scaphandre
PLATFORM = "JETSON" if "TEGRA" in os.popen(
    "uname -a").read().upper() else "DESKTOP"
BACKEND = "jtop" if PLATFORM == "JETSON" else "scaphandre"


logger.info(f"Detected platform: {PLATFORM}")
logger.info(f"Using backend: {BACKEND}")


request_queue = queue.Queue()


def run_cpu_measure(pids, duration):
    if BACKEND == "jtop":
        jtop_backend.log_dir = LOG_DIR
        jtop_backend.jtop_measure()
    elif BACKEND == "scaphandre":
        scaphandre_backend.cpu_measure(pids, "scaph",duration)


def run_gpu_measure(pids, duration):
    if BACKEND == "jtop":
        pass  # jtop measure cpu and gpu at the same time
    if BACKEND == "scaphandre":
        scaphandre_backend.gpu_measure(pids, "nvsmi", duration)


def run_power_measure(request_info):

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

    if (measure_cpu):
        cpu_thread = threading.Thread(
            target=run_cpu_measure, args=(pids, duration))
        cpu_thread.start()
    if (measure_gpu):
        gpu_thread = threading.Thread(
            target=run_gpu_measure, args=(pids, duration))
        gpu_thread.start()

    if (measure_cpu):
        cpu_thread.join()
    if (measure_gpu):
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
        send_monitor_power_start_fb_event(
            socket, my_pids, monitor_type, monitor_duration)
        logger.info("Send a testing power monitor event...")

    while not stop:
        message = get_next_msg(socket)
        logger.info("Got a message...")
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
    if TEST_FUNCTION:
        print("Debuging mode")
    run()
