#!/bin/bash
echo "Start of Image Scoring Plugin..."
if [ $MODEL_TYPE -eq 1 ]; then
  wget -q -O /md_v5a.0.0.pt https://github.com/ICICLE-ai/camera_traps/raw/main/models/md_v5b.0.0.pt
  echo "Executing the MDV5B second model. Downloading the model..."
fi

if [ $MODEL_TYPE -eq 2 ]; then
  wget -q -O /md_v5a.0.0.pt https://github.com/ICICLE-ai/camera_traps/raw/main/models/md_v5a.0.0_ena.pt
  echo "Executing the Megadetector fine-tuned ENA model. Downloading the model..."
fi

if [ $MODEL_TYPE -eq 3 ]; then
  wget -q -O /md_v5a.0.0.pt https://github.com/ICICLE-ai/camera_traps/raw/main/models/mdv5_optimized.pt
  echo "Executing the Megadetector optimized model. Downloading the model..."
fi

python -u image_scoring_plugin.py
