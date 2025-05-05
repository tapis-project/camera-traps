ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL
RUN chmod -R 0777 /* || true


ADD detection_reporter.py /detection_reporter.py
RUN pip install filelock toml
RUN chmod -R 0777 /detection_reporter.py || true 

ENTRYPOINT [ "python", "-u", "/detection_reporter.py" ]
