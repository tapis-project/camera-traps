ctevents
========
A python library for working with the Camera Traps events messages. This library provided
high-level convenience functions for easily sending and receiving Camera Traps events. 

There are three Docker images associated with this package, tapis/camera_traps_py, tapis/camera_traps_py_3.8, and
tapis/camera_traps_py_3.13; each image provides a tag for each release, for example:  
tapis/camera_traps_py:0.5.0, tapis/camera_traps_py_3.8:0.5.0, and tapis/camera_traps_py_3.13:0.5.0
for the 0.5.0 release. 

The images bundle a test file that can be executed directly in the image; for example: 

```
# start a container 
docker run -it --rm --entrypoint=bash tapis/camera_traps_py:0.5.0

# run the tests 
python test_ctevents.py
```

The test suite was not written with any test framework so no reporting is provided. Since all that was used was simple
assert statements, if the program executes completely (with no exception output), then the tests have all "passed". 
