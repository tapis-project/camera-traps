import os
import zmq
from ctevents import ctevents
from ctevents.ctevents import send_terminating_plugin_fb_event
from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
import logging
from subprocess import run, PIPE, STDOUT

log_level = os.environ.get("VIDEO_GENERATING_LOG_LEVEL", "INFO")
input_video_path = os.environ.get("INPUT_VIDEO_PATH", "/example_video.mp4")
ground_truth_file = os.environ.get("GROUND_TRUTH_FILE", "/ground_truth.yml")
device = os.environ.get("DEVICE", "http://0.0.0.0/8090")

logger = logging.getLogger("Image Generating Plugin")
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

def get_socket():
    """
    This function creates the zmq socket object and generates the event-engine plugin socket
    for the port configured for this plugin.
    """
    # get the port assigned to the Image Generating plugin
    PORT = os.environ.get('VIDEO_GENERATING_PLUGIN_PORT', 6000)
    # create the zmq context object
    context = zmq.Context()
    socket = get_plugin_socket(context, PORT)
    socket.RCVTIMEO = 100 # in milliseconds
    return socket

def get_video_duration():
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_video_path], stdout=PIPE, stderr=STDOUT)
    return ceil(float(result.stdout))


def load_ground_truth():
    return None
    with open(ground_truth_file, 'r') as f:
        video_info = yaml.safe_load(f)
    video_info['duration'] = get_video_duration()
    OUTPUT_DIR = os.environ.get('TRAPS_VIDEO_OUTPUT_PATH', '/output')
    video_info_file = os.path.join(OUTPUT_DIR, 'video_info.yaml')
    with open(video_info_file, 'w') as f:
        yaml.dump(video_info, f)

def monitor_generating_power():
    """
    This function is used to initiate the power monitoring event, if the monitoring flag is set.
    """
    monitor_flag = os.getenv('MONITOR_POWER')
    pid = [os.getpid()]
    monitor_type = [1]
    monitor_seconds = 0
    if monitor_flag:
        ctevents.send_monitor_power_start_fb_event(socket, pid, monitor_type, monitor_seconds)
        logger.info(f"Monitoring image generating power")

def is_v4l2loopback_available():
    out = run(['v4l2-ctl', '-d', device, '--all'], capture_output=True)
    for line in out.stdout.decode().splitlines():
        if line.strip().lower().startswith('driver name') and 'v4l2 loopback' in line.lower():
            return True
    return False

def stream_file_to_device(input_video_path):
    logger.info(f'starting video device stream to {device}')
    run(['ffmpeg', '-re', '-stream_loop', '-1', '-i', input_video_path, '-f', 'v4l2', '-pix_fmt', 'yuv420p', device])
    logger.info('Video stream finished')

def stream_file_to_netcam(input_video_path, device):
    logger.info(f'starting  netcam stream at {netcam_url}')
    run(['ffmpeg', '-re', '-i', input_video_path, '-f', 'mjpeg', '-pix_fmt', 'yuv420p',  '-listen', '1', netcam_url])
    logger.info('Video stream finished')

def get_device_type():
    if '/dev/video' in device:
        return 'video_device'
    elif 'http://' in device:
        return 'netcam'

def process_video(input_video_path, ground_truth):
    """
    Main function that starts a video stream, either on /dev/video or as a netcam
    """
    logger.info(f"The input video path specified by the user:{input_video_path}")
    device_type = get_device_type()
    if device_type == 'video_device':
        if is_v4l2loopback_available():
            stream_file_to_device(input_video_path)
        else:
            logger.info('v4l2loopback not available for {device}. Falling back to netcam stream.')
            stream_file_to_netcam(input_video_path, DEFAULT_NETCAM)
    else:
        stream_file_to_netcam(input_video_path)

def main():
    global socket
    socket = get_socket()
    ground_truth = load_ground_truth()
    monitor_generating_power()
    #motion_ready_signal(socket)
    process_video(input_video_path, ground_truth)
    send_quit_command(socket)

if __name__ == '__main__':
    logger.info("Video generating plugin starting...")
    main()
    logger.info("Video generating plugin exiting...")
