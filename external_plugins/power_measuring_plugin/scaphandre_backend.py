import csv
import datetime
import json
import subprocess
import time
import os
import sys
import logging

from power_measuring_plugin import stop

log_dir = os.environ['TRAPS_POWER_LOG_PATH']


logger = logging.getLogger("Power measurement")


# Command lines to use for the 
DEVICE_TYPES_METHODS = {"cpu": {"scaph": "sudo /scaphandre/target/release/scaphandre stdout -t "},
                        "gpu": {"nvsmi": "sudo nvidia-smi --query-gpu=index,power.draw --format=csv"}}


def cpu_measure(pids, cpu_method, duration):
    """
    Main wrapper function for measuring CPU consumption via the scaphandre backend. This function executes 
    scaphandre as a subprocess, processing stdout one line at a time via a pipe. 
    """
    # TODO: the cpu_method is defunct, as the only use of this function is for the schaphandre backend. 
    #       we should update the code to remove this variable. 
    if cpu_method is None:
        logger.warning(
            "No CPU method specified. Using default scaphandre method.")
        cpu_method = "scaph"
    # In this function, we are always measuring CPU only, so we always write to the cpu.json file
    file_name = "cpu.csv"

    # Determine the command line to execute in the subprocess
    method = DEVICE_TYPES_METHODS["cpu"][cpu_method]
    # Note that a duration of 0 in Camera Traps means "monitor forever", but the scaphandre CLI has changed recently and
    # does not run at all when a duration of 0 is passed, so we override it to a large number. 
    if duration == 0:
        duration = 31449600 # this is 1 year's worth of seconds
    cmd = method + str(duration)

    logger.info(f"Using scaphandre to start measuring PID: {pids} for duration: {duration}")
    
    # Start scaphandre in a subprocess -----
    logger.debug(f"Command line being started: {cmd}")
    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    # This variable maintains the power measurement data we collect from scaphandre.
    meta_infos = {}

    # Loop to process stdout from scaphandre; we read one line at a time and check for the PIDs 
    # we care about. 
    while not stop:
        output = process.stdout.readline()

        if output == "" and process.poll() is not None:
            logger.info(f"(PIDs {pids}) output from scaphandre was empty; this thread will exit...")
            break
        if output:
            current_time = datetime.datetime.now()
            readable_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
            temp_result = []
            for line in output.strip().splitlines():
                if line[-1] != '"':
                    continue
                # iterate through all the PIDs we are monitoring checking for the PID's occurrence in the output
                for pid in pids:
                    if str(pid) in line:
                        logger.debug(f"parsing stdout line: {line}")
                        meta_info = line.split('\t')
                        logger.debug(f"line splits: {meta_info}")
                        # Parse the line for different parts ----
                        # the power consumed, in wats
                        meta_info[0] = float(meta_info[0][:-2])
                        # the pid
                        meta_info[1] = meta_info[1]
                        # the first part of the command line -- this can be thrown away 
                        meta_info[2] = meta_info[2].strip('"')
                        # -----
                        logger.debug(f"(PIDs: {pids}) Adding the following output from scaphandre: {meta_info}")
                        
                        #meta_infos[readable_time] = meta_info
                        # For each time entry, the schema calls for a list of lists, with each inner list
                        # containing the pair of power measurement and pid 
                        # for JSON file:
                        # temp_result.append([meta_info[0], meta_info[1]])
                        # for CSV file:
                        temp_result.append([readable_time, meta_info[0], meta_info[1]])
        
            # Append the most recent entry to the file
            if len(temp_result) > 0:
                with open(os.path.join(log_dir, file_name), 'a') as f:
                    logger.debug(f"Appending to the CSV file for PIDs: {pids}")
                    csv_writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                    for r in temp_result:
                        csv_writer.writerow(r)
                # meta_infos[readable_time] = json.dumps(temp_result)
                # with open(os.path.join(log_dir, file_name), 'a') as json_file:
                #     json_file.write("{" + f'"{readable_time}": {meta_infos[readable_time]}' + "},\n")


def gpu_measure(pids, gpu_method, duration):
    """
    Main wrapper function for measuring GPU consumption via the scaphandre backend. 
    
    * * * 
        NOTE: this function if very confusing, as it actually uses the nvidia-smi tool, not the scaphandre tool
    * * * 
    
    This function executes nvsmi as a subprocess, processing stdout one line at a time via a pipe. 
    """
    # TODO: the gpu_method is also defunct, as the only use of this function is for the schaphandre backend. 
    #       we should update the code to remove this variable. 
    if gpu_method is None:
        logger.warning(
            "No GPU method specified. Using default nvidia-smi method.")
        gpu_method = "nvsmi"

    # In this function, we are always measuring GPU only, so we always write to the cpu.json file
    file_name = "gpu.json"

    # determine the command line to execute in the subprocess
    method = DEVICE_TYPES_METHODS["gpu"][gpu_method]
    cmd = method
    logger.info(f"Starting to measure GPU for the following PIDs: {pids}")
    logger.debug(f"GPU command line being started: {cmd} ")

    # The time, in seconds, that we sleep between calls to nvsmi. 
    time_interval = 2

    # This variable maintains the power measurement data we collect from nvsmi.
    meta_infos = {}

    # Main loop to start nvsmi as a subprocess and process the stdout
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
                    parts = line.split()[-2]
                    logger.debug(f"(PIDs: {pids}) Adding the following output from nvdia-smi: {parts}")
                    meta_infos[readable_time] = float(parts)
            with open(os.path.join(log_dir, file_name), 'a') as json_file:
                json.dump(meta_infos, json_file)

        process.wait()
        time.sleep(time_interval)
        duration -= time_interval
