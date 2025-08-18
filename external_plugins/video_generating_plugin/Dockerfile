ARG REL=use-build-arg
FROM tapis/camera_traps_py_3.13:$REL

# Update apt packages and install dependencies
RUN apt-get update && apt-get install -y ffmpeg v4l-utils libv4l-dev

ADD video_generating_plugin.py /video_generating_plugin.py
ADD example_video.mp4 /example_video.mp4
ADD ground_truth.yml /ground_truth.yml

RUN chmod -R 0777 /video_generating_plugin.py || true 

ENTRYPOINT [ "python", "-u", "/video_generating_plugin.py" ]
