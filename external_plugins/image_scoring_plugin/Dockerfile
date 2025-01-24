# Image: tapis/image_scoring_plugin_py
#
# Initial version of the Camera Traps Image Scoring Plugin, in Python.
# # This image is usually built by executing the top-level Makefile.  See
# that file to understand how the --build-arg parameter is used to set the 
# REL argument, which in turn specifies the generated image's tag.
#
# To run this program, you must mount a directory of image files at the mount point 
# specified in the input.json file. An example input.json file is provided which points to 
# `/input` in the container for the image directory, so if not changing the input file, mount the 
# directory of images here.
# 
# Examples:
#
# 1) If you want to run with the example input.json include with the image:
#    docker run tapis/image_scoring_plugin_py
#
# 2) If you want to specify a different input.json, do the following:
#    docker run -v /path/to/input.json:/input.json -v /path/to/images:/input/path tapis/image_generating_plugin_py
#
ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL
RUN chmod -R 0777 /* || true

RUN wget -O /md_v5a.0.0.pt https://github.com/microsoft/CameraTraps/releases/download/v5.0/md_v5a.0.0.pt

RUN git clone https://github.com/microsoft/CameraTraps \
    && git clone https://github.com/microsoft/ai4eutils \
    && git clone https://github.com/ultralytics/yolov5/ \
    && cd "/yolov5" && git checkout c23a441c9df7ca9b1f275e8c8719c949269160d1

RUN pip install -r requirements.txt

ENV PYTHONPATH=${PYTHONPATH}:/ai4eutils:/CameraTraps:/yolov5

ENV images_dir='/example_images/' 
ENV output_file_path='/example_images/detections.json'

ADD example_images /example_images
ADD entrypoint.sh /entrypoint.sh
ADD image_scoring_plugin.py /image_scoring_plugin.py

RUN chmod +x /entrypoint.sh
RUN chmod -R 0777 /example_images /entrypoint.sh /image_scoring_plugin.py /image_scoring_plugin.py || true 

ENTRYPOINT ["./entrypoint.sh"]
