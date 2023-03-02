#https://colab.research.google.com/drive/1lQRwqqLHvEEUN5hG9lzFiUXc1wlywCT3?usp=sharing

import json

f = open('/content/drive/MyDrive/ColabNotebooks/Image/detections.json')

data = json.load(f)
for i in data['images'] :
  for j in i['detections']:
    if(j['category']=="1" and i['max_detection_conf']==j['conf']):
      print(i["file"],j['conf'])


f.close()
