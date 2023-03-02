#!/bin/bash

python /CameraTraps/detection/run_detector_batch.py md_v5a.0.0.pt "$images_dir" "$output_file_path" --recursive --output_relative_filenames --quiet

python image_scoring_plugin.py
