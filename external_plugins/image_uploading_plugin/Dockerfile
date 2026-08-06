# Image: tapis/image_uploading_plugin_py

ARG REL=use-build-arg
FROM tapis/camera_traps_py_3.13:$REL
RUN find / -path /proc -prune -o -path /sys -prune -o -path /dev -prune -o -writable -print0 | xargs -0 -P $(nproc) -I {} chmod 0777 {} || true

RUN pip install Pillow toml
ADD image_uploading_plugin.py /image_uploading_plugin.py

RUN chmod -R 0777 /image_uploading_plugin.py  || true 

ENTRYPOINT [ "python", "-u", "/image_uploading_plugin.py" ]
