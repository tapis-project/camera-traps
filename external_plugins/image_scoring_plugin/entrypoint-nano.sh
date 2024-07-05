#!/bin/bash
echo "Start of Image Scoring Plugin..."
if [ "$MODEL_TYPE" -eq 1 ]; then
  wget -q -O /md_v5a.0.0.pt https://github.com/microsoft/CameraTraps/releases/download/v5.0/md_v5b.0.0.pt
  echo "Executing the second model. Downloading the model..."
fi

if [ "$MODEL_TYPE" -eq 2 ]; then
  wget -q -O /md_v5a.0.0.pt https://github.com/sowbaranika1302/Megadetector-model/raw/main/md_v5a.0.0.pt
  echo "Executing the third model. Downloading the model..."
fi

python3 -u image_scoring_plugin.py
