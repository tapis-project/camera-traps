# Image: tapis/image_detecting_plugin
ARG REL=use-build-arg
FROM tapis/camera_traps_py_3.13:$REL
RUN find / -path /proc -prune -o -path /sys -prune -o -path /dev -prune -o -writable -print0 | xargs -0 -P $(nproc) -I {} chmod 0777 {} || true

# Package dependencies 
RUN apt update && apt install -y motion vim
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
