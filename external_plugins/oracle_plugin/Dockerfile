ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL

ADD oracle_plugin.py /oracle_plugin.py

ENTRYPOINT [ "python", "-u", "/oracle_plugin.py" ]