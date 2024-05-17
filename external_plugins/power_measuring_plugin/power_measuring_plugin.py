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
import psutil
import threading
import subprocess
from copy import deepcopy
import jtop_backend
import scaphandre_backend


# Configure the logger -----
logger = logging.getLogger("Power measurement")

log_level = os.environ.get("TRAPS_POWER_LOG_LEVEL", "INFO")
if log_level == "DEBUG":
    logger.setLevel(logging.DEBUG)
elif log_level == "INFO":
    logger.setLevel(logging.DEBUG)
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

LOG_DIR = os.environ.get('TRAPS_POWER_LOG_PATH', "/logs/")

# Socket configuration 
PORT = os.environ.get('POWER_MEASURING_PLUGIN_PORT', 6010)

# Whether to run monitor this process as a test
TEST_FUNCTION = int(os.environ.get('TRAPS_TEST_POWER_FUNCTION', '0'))

# global to determine when to stop
stop = False


# Determine the backend to use based on the current platform. 
# Currently, two backends are supported: jtop and scaphandre
# We use the kernel version (uname -a) to 
PLATFORM = "JETSON" if "TEGRA" in os.popen(
    "uname -a").read().upper() else "DESKTOP"
BACKEND = "jtop" if PLATFORM == "JETSON" else "scaphandre"

# Devices to measure 
ALL_DEVICES = 0
CPU_DEVICE = 1
GPU_DEVICE = 2


request_queue = queue.Queue()


def run_cpu_measure(pids, duration):
    """
    Wrapper function for measuring CPU. This function wraps the main functions provided in the various backends.
    Note that duration is ignored by the jtop backend. 
    """
    if BACKEND == "jtop":
        jtop_backend.log_dir = LOG_DIR
        jtop_backend.jtop_measure()
    elif BACKEND == "scaphandre":
        scaphandre_backend.cpu_measure(pids, "scaph", duration)


def run_gpu_measure(pids, duration):
    """
    Wrapper function for measuring GPU. This function wraps the main functions provided in the various backends.
    """
    if BACKEND == "jtop":
        pass  # jtop measure cpu and gpu at the same time
    if BACKEND == "scaphandre":
        scaphandre_backend.gpu_measure(pids, "nvsmi", duration)


def run_power_measure(request_info):
    """
    This is the main power measuring function. It is started in a separate thread for each "task". 
    The `request_info` contains four pieces of information, as described in the original MonitorPowerStartEvent:
      * pids: a list of PIDs to monitor
      * devices: a list of devices to monitor, including CPU, GPU and all.
      * time_to_start: when to start measuring the power. NOTE: This parameter is currently ignored.
      * duration: how long to monitor the pids. NOTE: This parameter is ignored by the JTOP backend, and a value
                  of 0 indicates monitor indefinitely. 
    """

    # Parse data from the request
    pids, devices, time_to_start, duration = request_info

    # Determine which devices to measure 
    measure_cpu = False
    measure_gpu = False
    if ALL_DEVICES in devices:
        measure_cpu = True
        measure_gpu = True

    if CPU_DEVICE in devices:
        # cpu
        measure_cpu = True

    if GPU_DEVICE in devices:
        # gpu
        measure_gpu = True
    logger.info(f"New run_power_measure task starting for pids: {pids}; duration: {duration}; devices: {devices}")

    # Start the threads to measure the devices ---- 
    if (measure_cpu):
        logger.debug(f"Starting a new thread to measure CPU for the following PIDs: {pids}")
        cpu_thread = threading.Thread(
            target=run_cpu_measure, args=(pids, duration))
        cpu_thread.start()
    if (measure_gpu):
        logger.debug(f"Starting a new thread to measure GPU for the following PIDs: {pids}")
        gpu_thread = threading.Thread(
            target=run_gpu_measure, args=(pids, duration))
        gpu_thread.start()

    # Block on the threads completing 
    if (measure_cpu):
        cpu_thread.join()
    if (measure_gpu):
        gpu_thread.join()
    
    logger.info(f"Measurement threads have completed for the following PIDs: {pids}")


def watcher():
    """
    The watcher is started in a separate thread from the main program to read the internal queue 
    for power monitoring tasks. For each such task, this thread spawns a new thread to do the 
    actual monitoring. 
    """
    # watcher event loop ----
    while not stop:
        if not request_queue.empty():
            # get the next task to do 
            task = request_queue.get()

            # start a thread to monitor the power use
            t = threading.Thread(target=run_power_measure, args=(task,))
            t.start()


def get_socket():
    """
    This function creates the zmq socket object and generates the event-engine plugin socket
    for the port configured for this plugin.
    """
    return get_plugin_socket(zmq.Context(), PORT)


def get_base_metadata(start_time):
    """
    Returns the basic metadata object describing this execution.
    See the metadata.json example or the validate_schemas module for details. 
    """
    metadata = {
        "plugins": [],
        "tools": [],
        "start_time": start_time, 
        "last_update_time": None, 
    }
    # add the tools based on the backend
    if BACKEND == "jtop":
        # jtop measures both CPU and GPU at the same time ---- 
        metadata["tools"].append({
            		"device_type": "gpu",
		            "tool_name": "jtop",
		            "tool_params" : "",
		            "power_units": "watts",
                    # TODO 
		            "measurement_log_path": "/root/output/gpu.json"
        })
        metadata["tools"].append({
            		"device_type": "cpu",
		            "tool_name": "jtop",
		            "tool_params" : "",
		            "power_units": "watts",
                    # TODO 
		            "measurement_log_path": "/root/output/gpu.json"
        })
    # The "scaphandre" backend is actually a code word for using scaphandre for CPU measurements and 
    # nvidia-smi for GPU. 
    elif BACKEND == "scaphandre":
        metadata["tools"].append({
            		"device_type": "cpu",
		            "tool_name": "scaphandre",
		            "tool_params" : "scaphandre stdout -t ",
		            "power_units": "watts",
                    # TODO 
		            "measurement_log_path": "/root/output/gpu.json"
        })
        metadata["tools"].append({
            		"device_type": "gpu",
		            "tool_name": "nvidia-smi",
		            "tool_params" : "nvidia-smi --query-gpu=index,power.draw --format=csv",
		            "power_units": "watts",
                    # TODO 
		            "measurement_log_path": "/root/output/gpu.json"
        })

    return metadata

def get_pids_meta(pids, types):
    """
    Tries to look up the metadata associated with a process id. 
    """
    procs = {"name": [], "command_line": [], "devices_measured": []}
    if ALL_DEVICES in types:
        procs["devices_measured"] = ["cpu", "gpu"]
    else:
        if CPU_DEVICE in types:
            procs["devices_measured"].append("cpu")
        if GPU_DEVICE in types:
            procs["devices_measured"].append("gpu")
    for pid in pids:
        try:
            proc = psutil.Process(pid)
        except Exception as e:
            # raises a FileNotFoundError if pid no longer exists.
            continue
        name = proc.name()
        command_line = " ".join(proc.cmdline())
        # TODO: we use a hueristic here since we have no actual way of determing which plugin 
        #       is associated with the PID.
        if "image_generating_plugin.py" in command_line:
            name = "image_generating_plugin"
        elif "power_measuring_plugin.py" in command_line:
            name = "power_measuring_plugin"
        elif "image_scoring_plugin.py" in command_line:
            name = "image_scoring_plugin"

        logger.debug(f"Found proc for pid {pid}; name: {name}; cmdline: {command_line}")
        procs["name"].append(name)
        procs["command_line"].append(command_line)
    return procs 
    

def main():
    """
    Main loop of the power measuring plugin. This function instantiates the event socket, 
    starts the watcher thread, which processes message on the internal queue,
    and creates the event loop which processes MonitorPowerStart/Stop events. 
    """
    start_time = datetime.datetime.now()
    start_time_str = str(start_time).replace(" ", "")
    global stop
    logger.info("Power measuring plugin is starting...")
    logger.info(f"Detected platform: {PLATFORM}")
    logger.info(f"Using backend: {BACKEND}")

    # start the watcher in a new thread; the watcher is responsible for reading "tasks" from the internal
    # queue and starting processes that monitor power for each PID.
    watcher_thread = threading.Thread(target=watcher, args=())
    watcher_thread.start()

    # instantiate the event socket
    socket = get_socket()

    # The metadata about this execution; see the metadata.json example or the validate_schemas module
    metadata = get_base_metadata(start_time_str)

    # the TEST_FUNCTION controls whether this program monitors itself; if set to 1, it will 
    # monitor its own pid, allowing this program to be tested without the rest of the event engine.
    if TEST_FUNCTION == 1:
        my_pids = [os.getpid()]
        logger.info(f"Running in TEST mode, will monitor the usage of this plugin (PIDs: {my_pids}) for 10 seconds...")
        monitor_type = [0]
        monitor_duration = 10
        send_monitor_power_start_fb_event(
            socket, my_pids, monitor_type, monitor_duration)

    # Main event loop -- this loop waits for a new message on the event socket.
    # For each new MonitorPowerStart event, we create a task encapsulating the monitoring to be done, 
    # and we queue the task for a worker to receive and start the monitoring in a separate process. 
    while not stop:
        message = get_next_msg(socket)
        logger.info("Got a message from the event socket")
        event = socket_message_to_typed_event(message)
        
        # process a new MonitorPowerStart event ---- 
        if isinstance(event, MonitorPowerStartEvent):
            # pull various monitoring info out of the event: pids, types to monitor, start time and during
            pids = event.PidsAsNumpy().tolist()
            types = event.MonitorTypesAsNumpy()
            start_time = event.MonitorStartTs()
            duration = event.MonitorSeconds()
            pids_meta = get_pids_meta(pids, types)
            metadata["plugins"].append({
                "name": "; ".join(pids_meta["name"]),
                "pids": pids,
                "devices_measured": pids_meta["devices_measured"],
                "command_line": "; ".join(pids_meta['command_line']),
            })
            # bundle all of the monitoring info into a "task" and queue it
            task = [pids, types, start_time, duration]
            # queue the task so that a worker will pick it up 
            request_queue.put(deepcopy(task))
            logger.info(f"Message from event socket was a power monitor event for " + 
                        f"pids: {pids}, types: {types}; duration: {duration}; this task has been queued.")
        elif isinstance(event, MonitorPowerStopEvent):
            logger.info(f"Message from event socket was a MonitorPowerStop event; shutting down...")
            stop = True
        # Write the metadata file
        metadata["last_update_time"] = str(datetime.datetime.now()).replace(" ", "")
        with open(os.path.join(LOG_DIR, f"metadata_{start_time_str}.json"), 'w') as json_file:
                    json.dump(metadata, json_file)


if __name__ == "__main__":
    main()
