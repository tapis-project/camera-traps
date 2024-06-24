# Image: tapis/camera_traps_py
FROM tapis/pyevents

ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

ADD labrador-pup.jpg /labrador-pup.jpg
ADD ctevents /ctevents
ADD test_ctevents.py /test_ctevents.py
