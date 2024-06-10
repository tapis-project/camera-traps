import datetime
import docker
import logging 
import os 
import time 

from power_measuring_plugin import stop

log_dir = os.environ['TRAPS_POWER_LOG_PATH']
logger = logging.getLogger("Power measurement")


POWER_JOULAR_IMAGE = "jstubbs/powerjoular"

log_dir = os.environ['TRAPS_POWER_LOG_PATH']


def get_docker_client():
    """
    Get a docker client 
    """
    return docker.from_env()


def start_powerjoular(pid):
    """
    Start a separate docker container running the powerjoular program to monitor 
    the pid, `pid`. We configure powerjoular to write its output to a file in the 
    log directory named after the PID. 
    
    Returns the container id of the powerjoular container started, 

    """
    client = get_docker_client()

    # file name and output path for powerjoular to write the CSV 
    file_name = f"powerjoular_{pid}"
    output_path = os.path.join(log_dir, file_name)

    # Arguments to the powerjoular program; first we pass the PID to be monitored
    #   next, we pass the filename to use. the file names are "powerjoular" follows by 
    #         the PID we are monitoring. 
    powerjoular_args = f"-tp {pid} -f {output_path}"

    # We bind mount the logs directory into the powerjoular container so that it can 
    # write it's output to the shared directory. 

    volumes = { os.environ.get("TRAPS_POWER_LOG_HOST_PATH"): {
        "bind": log_dir, "mode": "rw"}
    }

    # run the powerjoular container
    logger.info(f"Starting a powerjoular conatiner for PID: {pid}")
    logger.debug(f"powerjoular container args: {powerjoular_args}; image: {POWER_JOULAR_IMAGE}")
    cid = client.containers.run(POWER_JOULAR_IMAGE, 
                                powerjoular_args, 
                                # we must run powerjoular in the host namespace so that it can 
                                # monitor the PID
                                pid_mode="host",
                                # mount a shared volume to write logs 
                                volumes=volumes,
                                # we must run powerjoular in privileged mode so that it can access 
                                # the program coutners through the Intel RAPL interface
                                privileged=True,
                                detach=True)
    return cid 

    
def cpu_measure(pids, duration):
    """
    Main wrapper function for measuring CPU & GPU consumption via the powerjoular backend. This function executes 
    powerjoular as a separate container, with the output ultimately being written to a shared directory. 
    """
    logger.info(f"powerjoular backend starting for PIDs: {pids} and duration: {duration}")
    # the set of container id's running powerjoular 
    containers = []
    
    # start up a powerjoular container for each PID:
    for pid in pids:
        containers.append(start_powerjoular(pid))
    
    # wait until told to stop by the main process or until duration 
    start = datetime.datetime.now()
    if duration > 0:
        td_duration = datetime.timedelta(seconds=duration)

    while not stop:
        time.sleep(1)
        now = datetime.datetime.now()
        run_time = now - start 
        if (duration > 0) and (run_time > td_duration):
            logger.info(f"Hit max duration ({duration}); stopping powerjoular container for PIDs {pids})")
            break 
    if stop:
        logger.info(f"Hit stop condition; stopping powerjoular container for PIDs {pids})")
    
    # shut down the containers
    logger.info(f"Stopping powerjoular containers for PIDs {pids}")
    client = get_docker_client()
    for cid in containers:
        try:
            cid.remove(force=True)
        except Exception as e: 
            logger.debug(f"Got exception trying to force remove container; id:{cid}; e: {e}")
        



    