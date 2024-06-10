import docker
import os 

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
    the pid, `pid`. We configure powerhoular to write its output to a file in the 
    log directory named after the PID. 

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
    
def cpu_measure(pids, cpu_method, duration):
    """
    Main wrapper function for measuring CPU & GPU consumption via the powerjoular backend. This function executes 
    powerjoular as a separate container, with the output ultimately being written to a shared directory. 
    """
    while not stop:



    