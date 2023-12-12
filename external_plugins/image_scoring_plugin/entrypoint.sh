#!/bin/bash

# Sleep while triton loads. TODO: Will replace with a better method.
sleep 20
python -u image_scoring_plugin.py
