from ctevents.ctevents import socket_message_to_typed_event, send_monitor_power_start_fb_event
from ctevents import MonitorPowerStartEvent, MonitorPowerStopEvent
from ctevents.gen_events import PluginTerminateEvent
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
from generate_power_summary import generate_power_summary

import os
import zmq
import json
import csv 
import time
import queue
import logging
import datetime
import psutil
import threading
import subprocess
from copy import deepcopy


# Configure the logger -----
logger = logging.getLogger("Power measurement")

log_level = os.environ.get("TRAPS_POWER_LOG_LEVEL", "INFO")
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

# Main directory where power measurement log files (cpu.json, gpu.json, etc) are written
LOG_DIR = os.environ.get('TRAPS_POWER_LOG_PATH', "/logs/")

# Socket configuration 
PORT = os.environ.get('POWER_MEASURING_PLUGIN_PORT', 6010)

# Whether to run monitor this process as a test
TEST_FUNCTION = int(os.environ.get('TRAPS_TEST_POWER_FUNCTION', '0'))

# global to determine when to stop
stop = False

# Devices to measure 
ALL_DEVICES = 1
CPU_DEVICE = 2
GPU_DEVICE = 3

# How long to wait, in milliseconds, for a new message. If we do not receive a message in this 
# amount of time, the power measuring plugin will exit. Since the power measuring plugin receives 
# all of its messages at the very beginning, this is effectively a max total runtime. 
# Set to 0 for unlimited time.
SOCKET_TIMEOUT = 2000

# The total number of PowerMonitorStart messages this plugin expects to receive over the life of 
# a single execution. Once it receives this number, it will wait SOCKET_TIMEOUT for additional messages 
# but once it receives a zmq timeout error (error.Again), it will being the max runtime counter. 
TOTAL_EXPECTED_POWER_MONITOR_START_MSGS = 3 

# Max run time, in seconds, for the power measuring plugin execution after receiving the expected number 
# of Power Monitor Start messages. The plugin will sleep this amount 
# to allow for the other plugins to complete their executions before generating the summary. 
MAX_RUN_TIME = 25

request_queue = queue.Queue()


def get_backend():
    """
    Determine which backend to use for measuring power. 
    """
    # first, determine the platform:
    kernel = os.popen("uname -a").read().upper()
    if "TEGRA" in kernel:
        platform = "JETSON"
    else:
        platform = "DESKTOP"

    # check if backend is set directly in the environment 
    backend = os.environ.get("TRAPS_POWER_BACKEND")
    if backend:
        logger.debug(f"Detected backend of {backend} set in environment ")
        return backend, platform
    
    # otherwise, try to automatically determine the best backend
    if platform == 'JETSON':
        return "jtop", platform
    else:
        return "scaphandre", platform
        

def run_cpu_measure(pids, duration, backend):
    """
    Wrapper function for measuring CPU. This function wraps the main functions provided in the various backends.
    Note that duration is ignored by the jtop backend. 
    """
    if backend == "jtop":
        import jtop_backend
        jtop_backend.log_dir = LOG_DIR
        jtop_backend.jtop_measure()
    elif backend == "scaphandre":
        import scaphandre_backend
        scaphandre_backend.cpu_measure(pids, "scaph", duration)
    elif backend == "powerjoular":
        import powerjoular_backend
        powerjoular_backend.cpu_measure(pids, duration)


def run_gpu_measure(pids, duration, backend):
    """
    Wrapper function for measuring GPU. This function wraps the main functions provided in the various backends.
    """
    if backend == "jtop":
        pass  # jtop measures cpu and gpu at the same time
    if backend == "powerjoular":
        pass  # powerjoular measures cpu and gpu at the same time
    if backend == "scaphandre":
        import scaphandre_backend
        scaphandre_backend.gpu_measure(pids, "nvsmi", duration)


def run_power_measure(request_info, backend):
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
    # TODO: This is a hack because there was confusion about the MonitorType values;
    #       should be removed once code review complete ----------
    if 0 in devices:
        devices.append(ALL_DEVICES)
    #        -----------------------------------------------------

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
        logger.debug(f"Starting a new thread to measure CPU for the following PIDs: {pids}; duration: {duration}; backend: {backend}")
        cpu_thread = threading.Thread(
            target=run_cpu_measure, args=(pids, duration, backend))
        cpu_thread.start()
    if (measure_gpu):
        logger.debug(f"Starting a new thread to measure GPU for the following PIDs: {pids}")
        gpu_thread = threading.Thread(
            target=run_gpu_measure, args=(pids, duration, backend))
        gpu_thread.start()

    # Block on the threads completing 
    if (measure_cpu):
        cpu_thread.join()
    if (measure_gpu):
        gpu_thread.join()
    
    logger.info(f"Measurement threads have completed for the following PIDs: {pids}")


def watcher(backend):
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
            t = threading.Thread(target=run_power_measure, args=(task, backend))
            t.start()


def get_socket():
    """
    This function creates the zmq socket object and generates the event-engine plugin socket
    for the port configured for this plugin.
    """
    return get_plugin_socket(zmq.Context(), PORT)


def get_base_metadata(start_time, backend):
    """
    Returns the basic metadata object describing this execution.
    See the metadata.json example or the validate_schemas module for details. 
    """
    metadata = {
        "plugins": [],
        "tools": { "devices": [] },
        "start_time": start_time, 
        "last_update_time": None, 
    }
    
    # add the tools based on the backend
    cpu_file_path = os.path.join(LOG_DIR, "cpu.json")
    gpu_file_path = os.path.join(LOG_DIR, "gpu.json")
    if backend == "jtop" or backend == "powerjoular":
        # jtop and powerjoular measure both CPU and GPU at the same time ---- 
        metadata["tools"]["devices"].append({
            		"device_type": "gpu",
		            "tool_name": backend,
		            "tool_params" : "",
		            "power_units": "watts",
		            "measurement_log_path": gpu_file_path,
        })
        metadata["tools"]["devices"].append({
            		"device_type": "cpu",
		            "tool_name": backend,
		            "tool_params" : "",
		            "power_units": "watts",
		            "measurement_log_path": cpu_file_path,
        })
    # The "scaphandre" backend is actually a code word for using scaphandre for CPU measurements and 
    # nvidia-smi for GPU. 
    elif backend == "scaphandre":
        metadata["tools"]["devices"].append({
            		"device_type": "cpu",
		            "tool_name": "scaphandre",
		            "tool_params" : "scaphandre stdout -t ",
		            "power_units": "watts",
		            "measurement_log_path": cpu_file_path,
        })
        metadata["tools"]["devices"].append({
            		"device_type": "gpu",
		            "tool_name": "nvidia-smi",
		            "tool_params" : "nvidia-smi --query-gpu=index,power.draw --format=csv",
		            "power_units": "watts",
		            "measurement_log_path": gpu_file_path,
        })

    # TODO: Remove the following code when conversion to CSV is complete. 
    # initialize log files 
    # with open(cpu_file_path, 'w+') as f:
    #     f.write("[\n")
    # with open(gpu_file_path, 'w+') as f:
    #     f.write("[\n")

    return metadata, cpu_file_path, gpu_file_path


def get_pids_meta(pids, types):
    """
    Tries to look up the metadata associated with a set PIDs for a specific plugin that has
    requested power monitoring. 
    """
    procs = {"name": [], "command_line": [], "devices_measured": []}
    if ALL_DEVICES in types:
        procs["devices_measured"] = ["cpu", "gpu"]
    else:
        if CPU_DEVICE in types:
            procs["devices_measured"].append("cpu")
        if GPU_DEVICE in types:
            procs["devices_measured"].append("gpu")
    
    # look up the process name and command line associated with each PID
    for pid in pids:
        try:
            proc = psutil.Process(pid)
        except Exception as e:
            logger.error(f"Got exception looking up PID {pid} with psutil; e: {e}")
            # raises a FileNotFoundError if pid no longer exists.
            continue
        name = proc.name()
        command_line = " ".join(proc.cmdline())
        # TODO: we use a heuristic here since we have no actual way of determining which plugin 
        #       is associated with the PID.
        if "image_generating_plugin.py" in command_line:
            name = "image_generating_plugin"
        elif "power_measuring_plugin.py" in command_line:
            name = "power_monitor_plugin"
        elif "image_scoring_plugin.py" in command_line:
            name = "image_scoring_plugin"
        elif "oracle_plugin.py" in command_line:
            name = "oracle_plugin"

        logger.debug(f"Found proc for pid {pid}; name: {name}; cmdline: {command_line}")
        procs["name"].append(name)
        procs["command_line"].append(command_line)
    return procs 
    

def convert_csv_files_to_json(cpu_file_path, gpu_file_path):
    """
    This function converts the csv files to json.
    """
    logger.debug("Converting CPU and GPU files to JSON")
    
    # do the same processing to both files
    for p in [cpu_file_path, gpu_file_path]:
        # the final result is a JSON list
        result = []
        csv_path = p.replace("json", "csv")
        if not os.path.exists(csv_path):
            logger.info(f"Did not find CSV path {csv_path}.")
            # write empty result to json file:
            with open(p, "w+") as f: 
                f.write("[]")
            continue
        with open(csv_path, 'r') as f: 
            reader = csv.reader(f)
            # for each row, get the time stamp, measurement and PID
            for line in reader:
                if not len(line) == 3:
                    logger.error(f"Unexpected line length in CSV file ({p}); line: {line}")
                    continue
                time_stamp = line[0]
                measurement = line[1]
                pid = line[2]
                result.append({time_stamp: [[measurement, pid]]})
        # write to json file:
        with open(p, "w+") as f: 
            json.dump(result, f)
        

def convert_powerjoular_csv_to_json(pids, cpu_file_path, gpu_file_path):
    """
    This function converts all CVS files generated by the powerjoular backend to JSON files. The
    powerjoular csv files are in a different format than those produced by the other backends. 
    """
    # the final result is a JSON list; since powerjoular measures both CPU and GPU, we collect them
    # at the same time.
    cpu_result = []
    gpu_result = []

    # For each PID, there should be a single file with the powerjoular measurements in the log 
    # directory. 
    for pid in pids:
        file_name = f"powerjoular_{pid}"
        full_path = os.path.join(LOG_DIR, file_name)
        if not os.path.exists(full_path):
            logger.info(f"Did not find powerjoular output for path {full_path}; skipping for PID {pid}")
            continue
        with open(full_path, 'r') as f: 
            reader = csv.reader(f)
            # for each row, get the time stamp, measurement and PID
            for line in reader:
                # There are 5 columns: 
                # Date,CPU Utilization,Total Power,CPU Power,GPU Power
                if not len(line) == 5:
                    logger.error(f"Unexpected line length in CSV file ({full_path}); line: {line}")
                    continue
                # skip the header row 
                if "Date" in line[0]:
                    continue
                # Parse the row
                time_stamp = line[0]
                cpu_power_measurement = line[3]
                gpu_power_measurement = line[4]
                cpu_result.append({time_stamp: [[cpu_power_measurement, pid]]})
                gpu_result.append({time_stamp: [[gpu_power_measurement, pid]]})
    
    # write to json file:
    with open(cpu_file_path, "w+") as f: 
        json.dump(cpu_result, f)
    with open(gpu_file_path, "w+") as f: 
        json.dump(gpu_result, f)
            

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
    
    backend, platform = get_backend()

    logger.info(f"Detected platform: {platform}")
    logger.info(f"Using backend: {backend}")

    # start the watcher in a new thread; the watcher is responsible for reading "tasks" from the internal
    # queue and starting processes that monitor power for each PID.
    watcher_thread = threading.Thread(target=watcher, args=(backend, ))
    watcher_thread.start()

    # instantiate the event socket
    socket = get_socket()

    # The metadata about this execution; see the metadata.json example or the validate_schemas module
    metadata, cpu_file_path, gpu_file_path = get_base_metadata(start_time_str, backend)

    # The list of all PIDs that ultimately get monitored. 
    all_pids = []

    # the TEST_FUNCTION controls whether this program monitors itself; if set to 1, it will 
    # monitor its own pid, allowing this program to be tested without the rest of the event engine.
    if TEST_FUNCTION == 1:
        power_monitor_plugin_pid = os.getpid()
        all_pids.append(power_monitor_plugin_pid)
        my_pids = [power_monitor_plugin_pid]
        logger.info(f"Running in TEST mode, will monitor the usage of this plugin (PIDs: {my_pids}) for 10 seconds...")
        monitor_type = [1]
        monitor_duration = 10
        send_monitor_power_start_fb_event(
            socket, my_pids, monitor_type, monitor_duration)

    # total number of monitor start event messages we have received 
    nbr_monitor_start_events = 0 

    # Main event loop -- this loop waits for a new message on the event socket.
    while not stop:
        socket = get_socket()
        try:
            message = get_next_msg(socket, timeout=SOCKET_TIMEOUT)
            # message = get_next_msg(socket)
        except Exception as e:
            # we got a resource temporarily unavailable error; sleep for a second and try again
            if isinstance(e, zmq.error.Again):
                logger.debug(f"Got a zmq.error.Again; i.e., waited {SOCKET_TIMEOUT} ms without getting a message")
                if nbr_monitor_start_events >= TOTAL_EXPECTED_POWER_MONITOR_START_MSGS:
                    logger.info(f"Already received {TOTAL_EXPECTED_POWER_MONITOR_START_MSGS} monitor start events; breaking out of loop.")
                    stop = True
                continue
            # we timed out waiting for a message; just check the max time and continue 
            logger.debug(f"Got exception from get_next_msg; type(e): {type(e)}; e: {e}")
            stop = True 
            logger.info("Power measuring plugin stopping due to timeout limit...")
            continue
        
        logger.info("Got a message from the event socket")
        event = socket_message_to_typed_event(message)
        
        # process a new MonitorPowerStart event ---- 
        if isinstance(event, MonitorPowerStartEvent):
            nbr_monitor_start_events += 1
            # pull various monitoring info out of the event: pids, types to monitor, start time and during
            pids = event.PidsAsNumpy().tolist()
            all_pids.extend(pids)
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
        elif isinstance(event, PluginTerminateEvent):
            if event.PluginUuid() == '*' or event.PluginName() == '*' or event.PluginName() == 'ext_power_monitor_plugin':
                logger.info(f"Message from event socket was a PluginTerminateEvent event; shutting down...")
                stop = True                
            
        # Write the metadata file
        metadata["last_update_time"] = str(datetime.datetime.now()).replace(" ", "")
        with open(os.path.join(LOG_DIR, f"metadata_{start_time_str}.json"), 'w') as json_file:
                    json.dump(metadata, json_file)
    
    # First, sleep to let the other plugin programs complete
    time.sleep(MAX_RUN_TIME)
    
    # Finalize the log files by cleaning up characters 
    if backend == "powerjoular":
        convert_powerjoular_csv_to_json(all_pids, cpu_file_path, gpu_file_path)
    else:
        convert_csv_files_to_json(cpu_file_path, gpu_file_path)

    # Generate report
    logger.info("Power measurement plugin preparing to exit; generating summary report...")
    generate_power_summary()
    logger.info("Power summary generating, plugin now exiting..")
    exit()



if __name__ == "__main__":
    main()
