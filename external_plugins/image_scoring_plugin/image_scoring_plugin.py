import json

f = open('/example_images/detections.json')

data = json.load(f)
for i in data['images'] :
  for j in i['detections']:
    if(j['category']=="1" and i['max_detection_conf']==j['conf']):
      print(i["file"],j['conf'])


f.close()
