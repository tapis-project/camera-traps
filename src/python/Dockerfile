# Image: tapis/camera_traps_py
FROM tapis/pyevents

ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD labrador-pup.jpg /labrador-pup.jpg
ADD ctevents/gen_events /gen_events
ADD ctevents/ctevents.py /ctevents.py
