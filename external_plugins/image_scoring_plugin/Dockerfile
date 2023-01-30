# Image: tapis/image_scoring_plugin_py
#
# Initial version of the Camera Traps Image Scoring Plugin, in Python.
# To run this program, you must mount a directory of image files at the mount point 
# specified in the input.json file. An example input.json file is provided which points to 
# `/input` in the container for the image directory, so if not changing the input file, mount the 
# directory of images here.
# 
# Examples:
#
# 1) If you want to run with the example input.json include with the image:
#    docker run -v /path/to/images:/input tapis/image_generating_plugin_py
#
# 2) If you want to specify a different input.json, do the following:
#    docker run -v /path/to/input.json:/input.json -v /path/to/images:/input/path tapis/image_generating_plugin_py
#
FROM tapis/camera_traps_py

RUN pip install humanfriendly jsonpickle
RUN pip install torch==1.10.1 torchvision==0.11.2

RUN wget -O /content/md_v5a.0.0.pt https://github.com/microsoft/CameraTraps/releases/download/v5.0/md_v5a.0.0.pt

RUN git clone https://github.com/microsoft/CameraTraps 
RUN git clone https://github.com/microsoft/ai4eutils 
RUN git clone https://github.com/ultralytics/yolov5/
WORKDIR "/yolov5"
RUN git checkout c23a441c9df7ca9b1f275e8c8719c949269160d1

RUN import os
ENV os.environ['PYTHONPATH'] += ":/content/ai4eutils" 
ENV os.environ['PYTHONPATH'] += ":/content/CameraTraps" 
ENV os.environ['PYTHONPATH'] += ":/content/yolov5"

ADD image_scoring_plugin.py /image_scoring_plugin.py

ENV images_dir = '/examples_images/'
ENV output_file_path = '/example_images/detections.json'

RUN python /CameraTraps/detection/run_detector_batch.py md_v5a.0.0.pt "$images_dir" "${output_file_path}" --recursive --output_relative_filenames --quiet

ENTRYPOINT [ "python", "/image_scoring_plugin.py"]