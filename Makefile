# Build the Camera-Trap application and External Plugin Images
#
# The environment variable TRAPS_REL must be set before calling make;
# its value will be the tag assigned to all images that get built.
#
# To build all images follow these steps:
#
# 1. Export the TRAPS_REL environment variable value.  
# 2. Issue make with one of the build targets.  
#    Example: 'make build' builds all targets.

build-engine:
	docker build -t tapis/camera_traps_engine:${TRAPS_REL} .

build-camerapy:
	cd src/python && docker pull tapis/pyevents; docker pull tapis/pyevents:3.8; docker build -t tapis/camera_traps_py:${TRAPS_REL} . && docker build -t tapis/camera_traps_py_3.8:${TRAPS_REL} -f Dockerfile-3.8 .; cd ../../

build-scoring:
	cd external_plugins/image_scoring_plugin/ && docker build -t tapis/image_scoring_plugin_py_3.8:${TRAPS_REL} --build-arg REL=${TRAPS_REL} -f Dockerfile-3.8 .; cd ../..

build-generating:
	cd external_plugins/image_generating_plugin/ && docker build -t tapis/image_generating_plugin_py:${TRAPS_REL} --build-arg REL=${TRAPS_REL} .; cd ../..

build-py-plugins: build-camerapy build-scoring build-generating

build: build-engine build-py-plugins
