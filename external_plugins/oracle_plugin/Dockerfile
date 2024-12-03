ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL
RUN chmod -R 0777 /* || true


ADD oracle_plugin.py /oracle_plugin.py
RUN chmod -R 0777 /oracle_plugin.py || true 

ENTRYPOINT [ "python", "-u", "/oracle_plugin.py" ]