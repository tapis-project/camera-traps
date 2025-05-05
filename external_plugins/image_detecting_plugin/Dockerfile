# Image: tapis/image_detecting_plugin
ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL
RUN chmod -R 0777 /* || true

# Package dependencies 
RUN apt update && apt install -y motion 
RUN pip install watchdog
RUN pip install PILLOW

# Config files
ADD motion.default /etc/default/motion
ADD motion.conf /etc/motion/motion.conf

# Code 
ADD image_detecting_plugin.py /image_detecting_plugin.py
ADD entry.sh /entry.sh 

RUN chmod -R 0777 /oracle_plugin.py || true 


ENTRYPOINT [ "/entry.sh" ]
