ARG REL=use-build-arg
FROM tapis/camera_traps_py_3.13:$REL
RUN find / -path /proc -prune -o -path /sys -prune -o -path /dev -prune -o -writable -print0 | xargs -0 -P $(nproc) -I {} chmod 0777 {} || true



ADD oracle_plugin.py /oracle_plugin.py
RUN pip install filelock
RUN chmod -R 0777 /oracle_plugin.py || true 

ENTRYPOINT [ "python", "-u", "/oracle_plugin.py" ]
