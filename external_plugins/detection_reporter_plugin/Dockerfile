ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL
RUN find / -path /proc -prune -o -path /sys -prune -o -path /dev -prune -o -writable -print0 | xargs -0 -P $(nproc) -I {} chmod 0777 {} || true


ADD detection_reporter.py /detection_reporter.py
RUN pip install filelock toml
RUN chmod -R 0777 /detection_reporter.py || true 

ENTRYPOINT [ "python", "-u", "/detection_reporter.py" ]
