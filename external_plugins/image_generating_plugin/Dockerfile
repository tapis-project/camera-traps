# Image: tapis/image_generating_plugin_py
#
# Initial version of the Camera Traps Image Generating Plugin, in Python.
# To run this program, you must mount a directory of image files at the mount point 
# specified in the input.json file. An example input.json file is provided which points to 
# `/example_images` in the container for the image directory, so if not changing the input file, mount the 
# directory of images here.
# 
# Examples:
#
# 1) If you want to run with the example input.json include with the image:
#    docker run -v $(pwd)/example_images:/example_images tapis/image_generating_plugin_py
#
# 2) If you want to specify a different input.json, do the following:
#    docker run -v /path/to/input.json:/input.json -v /path/to/images:/input/path tapis/image_generating_plugin_py
#
ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL

RUN pip install opencv-contrib-python-headless 
RUN pip install PILLOW

ADD input_example.json /input.json
ADD image_generating_plugin.py /image_generating_plugin.py

ENTRYPOINT [ "python", "-u", "/image_generating_plugin.py" ]