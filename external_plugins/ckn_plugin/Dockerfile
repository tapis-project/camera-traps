ARG REL=use-build-arg
FROM tapis/camera_traps_py_3.13:$REL
RUN find / -path /proc -prune -o -path /sys -prune -o -path /dev -prune -o -writable -print0 | xargs -0 -P $(nproc) -I {} chmod 0777 {} || true

# Install confluent-kafka for Kafka producer functionality
RUN pip install confluent-kafka watchdog PyYaml || true

ADD ckn_plugin.py /ckn_plugin.py
RUN chmod -R 0777 /ckn_plugin.py || true 

ENTRYPOINT [ "python", "-u", "/ckn_plugin.py" ]

