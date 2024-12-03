# Image Scoring Plugin

The image scoring plugin uses computer vision algorithms to "score" images based on the 
likelihood of the image containing animals of interest. The current implementation 
makes use of the MicroSoft MegaDetector package, which in turn is based on Yolov5. 


## Docker Image ##

Two docker images are currently available -- one based on Python 3.8 and one based on Python 
3.10. These images are designed to run on x86/64 bit Linux and, optionally, Nvidia GPU. We 
are currently working on additional container images for ARM architectures, including 
edge devices such as the Jetson series. 


## Nix ##

We are also exploring packaging the image scoring plugin code using Nix. The flake in the 
repo can be used to build a development environment: 

```
nix develop 
```

This builds the flake and drops you into a Nix environment with Python 3.8.16, the image scoring 
plugin source code as well as all dependencies installed. From there, the load tests can 
be run with: 

```
python `realpath load_test_image_scoring.py`
```

Note that `realpath` is required at this time, as the image scoring plugin code currently 
makes certain assumptions about the location of `python` relative to the model file. 