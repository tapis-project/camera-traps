
build-engine:
	docker build -t tapis/camera_traps_engine .

build-camerapy:
	cd src/python && docker build -t tapis/camera_traps_py . && docker build -t tapis/camera_traps_py:3.8 -f Dockerfile-3.8 .; cd ../../

build-scoring:
	cd external_plugins/image_scoring_plugin/ && docker build -t tapis/image_scoring_plugin_py:3.8 -f Dockerfile-3.8 .; cd ../..

build-generating:
	cd external_plugins/image_generating_plugin/ && docker build -t tapis/image_generating_plugin_py .; cd ../..

build-py-plugins: build-camerapy build-scoring build-generating

build: build-engine build-py-plugins
