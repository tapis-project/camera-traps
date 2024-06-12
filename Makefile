# Build the Camera-Trap application and External Plugin Images
#
# The environment variable TRAPS_REL must be set before calling make;
# its value will be the tag assigned to all images that get built.
# For example:
#
#    export TRAPS_REL=0.3.3
#    export TRAPS_REL=0.3.
#
# NOTE: Right now, building with tag `latest` is not supported. Instead,
#       build a semantic version and then tag the result as latest.
#
# To build all images follow these steps:
#
# 1. Export the TRAPS_REL environment variable value.  
# 2. Issue make with one of the build targets.  
#    Example: 'make build' builds all targets.

build-engine:
	docker build -t tapis/camera_traps_engine:${TRAPS_REL} --build-arg TRAPS_REL=${TRAPS_REL} .

build-camerapy:
	cd src/python && docker pull tapis/pyevents; docker pull tapis/pyevents:3.8; docker build -t tapis/camera_traps_py:${TRAPS_REL} . && docker build -t tapis/camera_traps_py_3.8:${TRAPS_REL} -f Dockerfile-3.8 .; cd ../../

build-scoring:
	cd external_plugins/image_scoring_plugin/ && docker build -t tapis/image_scoring_plugin_py_3.8:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.8 .; cd ../..

build-generating:
	cd external_plugins/image_generating_plugin/ && docker build -t tapis/image_generating_plugin_py:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-power:
	cd external_plugins/power_measuring_plugin/ && docker build -t tapis/power_measuring_plugin_py:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-oracle:
	cd external_plugins/oracle_plugin/ && docker build -t sowbaranika1302/oracle_plugin:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-py-plugins: build-camerapy build-scoring build-generating build-power build-oracle

build: build-engine build-py-plugins

tag: build
	docker tag tapis/camera_traps_py:${TRAPS_REL} tapis/camera_traps_py & docker tag tapis/camera_traps_py_3.8:${TRAPS_REL} tapis/camera_traps_py_3.8 & docker tag tapis/image_scoring_plugin_py_3.8:${TRAPS_REL} tapis/image_scoring_plugin_py_3.8 & docker tag tapis/image_generating_plugin_py:${TRAPS_REL} tapis/image_generating_plugin_py & docker tag tapis/power_measuring_plugin_py:${TRAPS_REL} tapis/power_measuring_plugin_py & docker tag tapis/camera_traps_engine:${TRAPS_REL} tapis/camera_traps_engine & docker tag sowbaranika1302/oracle_plugin:${TRAPS_REL} sowbaranika1302/oracle_plugin

push: tag
	docker push tapis/camera_traps_py & docker push tapis/camera_traps_py:${TRAPS_REL} & docker push tapis/camera_traps_py_3.8 & docker push tapis/camera_traps_py_3.8:${TRAPS_REL} & docker push tapis/image_scoring_plugin_py_3.8 & docker push tapis/image_scoring_plugin_py_3.8:${TRAPS_REL} & docker push tapis/image_generating_plugin_py & docker push tapis/image_generating_plugin_py:${TRAPS_REL} & docker push tapis/power_measuring_plugin_py:${TRAPS_REL} & docker push sowbaranika1302/oracle_plugin:${TRAPS_REL} & docker push tapis/camera_traps_engine & docker push tapis/camera_traps_engine:${TRAPS_REL}
