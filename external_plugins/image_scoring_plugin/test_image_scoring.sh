#!/bin/bash

# docker run -it --entrypoint=bash -v $(pwd)/example_images:/example_images --rm tapis/image_scoring_plugin_py_3.8
#
# python 
# from camera_traps_MD.run_detector import load_and_run_detector
# DEFAULT_BOX_THICKNESS = 4
# DEFAULT_BOX_EXPANSION = 0
# CROP_IMAGE = False
# IMAGE_SIZE = None
# 
# image_file_path = "/example_images/labrador-pup.jpg"
# base_path = "/"
# image_path_prefix = "output"
#
# results= load_and_run_detector(model_file="md_v5a.0.0.pt", image_file_names=[image_file_path], output_dir=f"{base_path}/{image_path_prefix}", render_confidence_threshold=0.1, box_thickness=DEFAULT_BOX_THICKNESS, box_expansion=DEFAULT_BOX_EXPANSION, crop_images=CROP_IMAGE, image_size=IMAGE_SIZE)