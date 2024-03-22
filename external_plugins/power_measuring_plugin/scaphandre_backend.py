import datetime
import json
import subprocess
import time
import os
import sys
import logging

from power_measuring_plugin import stop

log_dir = os.environ['TRAPS_POWER_LOG_PATH']
file_name = 'jtop_log.json'

logger = logging.getLogger("Power measurement")


DEVICE_TYPES_METHODS = {"cpu": {"scaph": "scaphandre stdout -t "},
                        "gpu": {"nvsmi": "nvidia-smi --query-gpu=index,power.draw --format=csv"}}


def cpu_measure(pids, cpu_method, duration):
    if cpu_method is None:
        logger.warning(
            "No CPU method specified. Using default scaphandre method.")
        cpu_method = "scaph"
    method = DEVICE_TYPES_METHODS["cpu"][cpu_method]
    cmd = method + str(duration)
    logger.info("start measuring PID={} CPU for {}s using {}".format(
        pids, duration, cpu_method))

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
            with open(os.path.join(log_dir, file_name), 'w') as json_file:
                json.dump(meta_infos, json_file)


def gpu_measure(pids, gpu_method, duration):
    if gpu_method is None:
        logger.warning(
            "No GPU method specified. Using default nvidia-smi method.")
        gpu_method = "nvsmi"
    method = DEVICE_TYPES_METHODS["gpu"][gpu_method]
    cmd = method
    logger.info("start measuring PID={} GPU for {}s using {}".format(
        pids, duration, gpu_method))
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
            with open(os.path.join(log_dir, file_name), 'w') as json_file:
                json.dump(meta_infos, json_file)

        process.wait()
        time.sleep(time_interval)
        duration -= time_interval
