import csv
import datetime
from jtop import jtop
import logging 
import json
import time
import os
import sys

from power_measuring_plugin import stop

logger = logging.getLogger("Power measurement")

log_dir = os.environ['TRAPS_POWER_LOG_PATH']


def jtop_measure(pids):
    """
    Main wrapper function for measuring CPU and GPU utilization with the JTOP backend. This 
    function uses the jetson Python SDK (jetson-stats on PyPI) to measure both CPU and GPU 
    power consumed. 
    """
    logger.info(f"jtop_measure starting for pids: {pids}")
    cpu_log_file = os.path.join(log_dir, "cpu.csv")
    gpu_log_file = os.path.join(log_dir, "gpu.csv")
    tot_log_file = os.path.join(log_dir, "tot_power_jtop.csv")
    
    # TODO: for now, we do not have the ability to measure per PID, so we report everything for the 
    #       the first PID sent. 
    pid = pids[0]

    while not stop:
        # get the current usage
        current_time, cpu, gpu, tot = read_stats()
        logger.debug(f"Got new JTOP measurement: {current_time}, {cpu}, {gpu}, {tot}")
        
        # write the usage to each file 
        with open(os.path.join(log_dir, cpu_log_file), 'a') as f:
            logger.debug(f"Appending to the CPU CSV file for PID: {pid}")
            csv_writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            csv_writer.writerow([current_time, cpu, pid])        

        with open(os.path.join(log_dir, gpu_log_file), 'a') as f:
            logger.debug(f"Appending to the GPU CSV file for PID: {pid}")
            csv_writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            csv_writer.writerow([current_time, gpu, pid])

        with open(os.path.join(log_dir, tot_log_file), 'a') as f:
            logger.debug(f"Appending to the TOTAL CSV file for PID: {pid}")
            csv_writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            csv_writer.writerow([current_time, tot, pid])
        
        # measure every 1 second
        time.sleep(1)       


def read_stats():
    """
    Function to read the instantaneous CPU, GPU and total power consumption using the jtop backend.
    This function returns three values: cpu_consumed, gpu_consumed and tot_consumed.
    """
    current_time = datetime.datetime.now()
    readable_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    cpu = 0
    gpu = 0
    tot = 0
    with jtop() as jetson:
        if jetson.ok():
            data = jetson.power
            
            # note that the power measurements returned from the "power" keys are in milliwatt, as per
            # https://rnext.it/jetson_stats/reference/jtop.html#jtop.jtop.power
            
            # CPU ----
            try: 
                cpu = data["rail"]["POM_5V_CPU"]["power"]
                # convert milliwatt to watt
                cpu = float(cpu) / 1000
            except Exception as e:
                logger.error(f"Got exception trying to read CPU power; e: {e}; data: {data}")

            # GPU ----
            try: 
                gpu = data["rail"]["POM_5V_GPU"]["power"]
                # convert milliwatt to watt
                gpu = float(gpu) / 1000
            except Exception as e:
                logger.error(f"Got exception trying to read GPU power; e: {e}; data: {data}")

            # TOTAL ----
            try: 
                tot = data["tot"]["power"]
                # convert milliwatt to watt
                tot = float(tot) / 1000
            except Exception as e:
                logger.error(f"Got exception trying to read TOTAL power; e: {e}; data: {data}")

        else:
            logger.error(f"Could not read jetson power; jetson.ok() returned false")
        
        return readable_time, cpu, gpu, tot
            

