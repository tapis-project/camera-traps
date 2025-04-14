#!/bin/bash

# Start the motion program to monitor the /data directory
service motion start

# Start the image detecting plugin 
python -u image_detecting_plugin.py 