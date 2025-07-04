# Build the Camera-Trap application and External Plugin Images
#
# The environment variable TRAPS_REL must be set before calling make;
# its value will be the tag assigned to all images that get built.
# For example:
#
#    export TRAPS_REL=0.5.0
#    export TRAPS_REL=0.5.
#
# NOTE: Right now, building with tag `latest` is not supported. Instead,
#       build a semantic version and then tag the result as latest.
#
# To build all images follow these steps:
#
# 1. Export the TRAPS_REL environment variable value.  
# 2. Issue make with one of the build targets.  
#    Example: 'make build' builds all targets.

clean:
	cd releases/${TRAPS_REL}; rm -rf power_output_dir/*; rm -rf images_output_dir/*; rm -rf oracle_plugin_dir/*; 

build-engine:
	docker build -t tapis/camera_traps_engine:${TRAPS_REL} --build-arg TRAPS_REL=${TRAPS_REL} .

build-camerapy:
	cd src/python && docker pull tapis/pyevents; docker pull tapis/pyevents:3.8; docker pull tapis/pyevents:3.13; docker build -t tapis/camera_traps_py:${TRAPS_REL} . && docker build -t tapis/camera_traps_py_3.8:${TRAPS_REL} -f Dockerfile-3.8 . && docker build -t tapis/camera_traps_py_3.13:${TRAPS_REL} -f Dockerfile-3.13 .; cd ../../

build-scoring-server:
	cd external_plugins/image_scoring_plugin/ && docker build -t tapis/image_scoring_plugin_server_py_3.13:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.13-server .; cd ../..

build-scoring-ultralytics:
	cd external_plugins/image_scoring_plugin/ && docker build -t tapis/image_scoring_plugin_ultralytics_py_3.13:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.13-ultralytics .; cd ../..

build-scoring-yolov5:
	cd external_plugins/image_scoring_plugin/ && docker build -t tapis/image_scoring_plugin_yolov5_py_3.8:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.8-yolov5 .; cd ../..

build-scoring-nano:
	cd external_plugins/image_scoring_plugin/ && docker build --platform linux/arm64 -t tapis/image_scoring_plugin_py_nano_3.8:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.8-nano .; cd ../..

build-scoring-nano-ultralytics:
	cd external_plugins/image_scoring_plugin/ && docker build --platform linux/arm64 -t tapis/image_scoring_plugin_py_nano_ultralytics_3.8:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.8-nano-ultralytics .; cd ../..


build-generating:
	cd external_plugins/image_generating_plugin/ && docker build -t tapis/image_generating_plugin_py:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-power:
	cd external_plugins/power_measuring_plugin/ && docker build -t tapis/powerjoular -f Dockerfile-powerjoular . && docker build -t tapis/scaphandre -f Dockerfile-scaphandre . && docker build -t tapis/power_measuring_plugin_py:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-oracle:
	cd external_plugins/oracle_plugin/ && docker build -t tapis/oracle_plugin:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-detection:
	cd external_plugins/detection_reporter_plugin && docker build -t tapis/detection_reporter_plugin:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-detecting:
	cd external_plugins/image_detecting_plugin && docker build -t tapis/image_detecting_plugin:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-py-plugins: build-camerapy build-scoring-server build-generating build-power build-oracle build-detection build-detecting

build-installer: 
	cd installer && docker build -t tapis/camera-traps-installer:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../

build: build-engine build-py-plugins build-installer

tag: build
	docker tag tapis/camera_traps_py:${TRAPS_REL} tapis/camera_traps_py & docker tag tapis/camera_traps_py_3.8:${TRAPS_REL} tapis/camera_traps_py_3.8 & docker tag tapis/image_scoring_plugin_py_3.8:${TRAPS_REL} tapis/image_scoring_plugin_py_3.8 & docker tag tapis/image_scoring_plugin_py_nano_3.8:${TRAPS_REL} tapis/image_scoring_plugin_py_nano_3.8 & docker tag tapis/image_generating_plugin_py:${TRAPS_REL} tapis/image_generating_plugin_py & docker tag tapis/power_measuring_plugin_py:${TRAPS_REL} tapis/power_measuring_plugin_py & docker tag tapis/camera_traps_engine:${TRAPS_REL} tapis/camera_traps_engine & docker tag tapis/oracle_plugin:${TRAPS_REL} tapis/oracle_plugin & docker tag tapis/camera-traps-installer:${TRAPS_REL} tapis/camera-traps-installer

push: tag
	docker push tapis/camera_traps_py & docker push tapis/camera_traps_py:${TRAPS_REL} & docker push tapis/camera_traps_py_3.8 & docker push tapis/camera_traps_py_3.8:${TRAPS_REL} & docker push tapis/image_scoring_plugin_py_3.8 & docker push tapis/image_scoring_plugin_py_3.8:${TRAPS_REL} & docker push tapis/image_scoring_plugin_py_nano_3.8 & docker push tapis/image_scoring_plugin_py_nano_3.8:${TRAPS_REL} & docker push tapis/image_generating_plugin_py & docker push tapis/image_generating_plugin_py:${TRAPS_REL} & docker push tapis/power_measuring_plugin_py:${TRAPS_REL} & docker push tapis/oracle_plugin:${TRAPS_REL} & docker push tapis/camera_traps_engine & docker push tapis/camera_traps_engine:${TRAPS_REL} & docker push tapis/camera-traps-installer:${TRAPS_REL} & docker push tapis/camera-traps-installer

push-all:
	docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/camera_traps_engine:${TRAPS_REL} --build-arg TRAPS_REL=${TRAPS_REL} .
	cd src/python && docker pull tapis/pyevents; docker pull tapis/pyevents:3.8; docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/camera_traps_py:${TRAPS_REL} . && docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/camera_traps_py_3.8:${TRAPS_REL} -f Dockerfile-3.8 .; cd ../../
	cd external_plugins/image_scoring_plugin/ && docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/image_scoring_plugin_py_3.8:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.8 .; cd ../..
	cd external_plugins/image_scoring_plugin/ && docker buildx build --platform linux/arm64 -t tapis/image_scoring_plugin_py_nano_3.8:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.8-nano .; cd ../..
	cd external_plugins/image_generating_plugin/ && docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/image_generating_plugin_py:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..
	cd external_plugins/power_measuring_plugin/ && docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/power_measuring_plugin_py:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..
	cd external_plugins/oracle_plugin/ && docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/oracle_plugin:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..
	cd installer && docker buildx build --platform linux/arm64,linux/amd64 --push -t tapis/camera-traps-installer:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../
