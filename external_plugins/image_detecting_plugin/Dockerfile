# Image: tapis/image_detecting_plugin
ARG REL=use-build-arg
FROM tapis/camera_traps_py_3.13:$REL
RUN find / -path /proc -prune -o -path /sys -prune -o -path /dev -prune -o -writable -print0 | xargs -0 -P $(nproc) -I {} chmod 0777 {} || true

# Package dependencies 
RUN apt update && apt install -y motion vim ffmpeg v4l-utils
RUN pip install watchdog
RUN pip install PILLOW
RUN pip install PyYaml

# Config files
ADD motion.default /etc/default/motion
ADD motion.conf /etc/motion/motion.conf
RUN mkdir /var/log/motion

# Code 
ADD image_detecting_plugin.py /image_detecting_plugin.py
ADD entry.sh /entry.sh 

RUN chmod -R 0777 /image_detecting_plugin.py || true


ENTRYPOINT [ "/entry.sh" ]
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD test -f /tmp/ready || exit 1
