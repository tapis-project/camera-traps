"""
Load test program for the Image Scoring plugin.

You can manually run this program inside the image scoring plugin docker container:

1) Run with examples images included in the repo 
docker run -it --rm --entrypoint=bash tapis/image_scoring_plugin_py_3.8
$ python load_test_image_scoring.py

2) Mount a separate directory of images and set additional args
docker run -it -v /home/jstubbs/traps/input/images_100/images_100:/example_images --rm --entrypoint=bash tapis/image_scoring_plugin_py_3.8

$ export MAX_IMAGES_TO_SCORE=25
$ python load_test_image_scoring.py
"""

import os
import time

from camera_traps_MD.run_detector import load_and_run_detector
from run_detector_multi import load_detector, run_detector
from image_scoring_plugin import DEFAULT_BOX_THICKNESS, DEFAULT_BOX_EXPANSION, CROP_IMAGE, IMAGE_SIZE


IMAGES_DIR_PATH = os.environ.get('IMAGES_DIR_PATH', 'example_images')
OUTPUT_DIR_PATH = os.environ.get('OUTPUT_DIR_PATH', os.getcwd())
SLEEP_TIME_PER_IMAGE = int(os.environ.get('SLEEP_TIME_PER_IMAGE', 0))
MAX_IMAGES_TO_SCORE = int(os.environ.get('MAX_IMAGES_TO_SCORE', 10))

# whether to cache the detector or to use the old method "load_and_run_detector()" method on each image
# export any other value to use the old method.
DEFAULT_MODE = 'cache_detector'
MODE = os.environ.get('MODE', DEFAULT_MODE)


def get_images():
    """
    Returns the paths of all images to use in the load test as a Python list of strings.
    """
    return [os.path.join(IMAGES_DIR_PATH, f) for f in os.listdir(IMAGES_DIR_PATH)] #if os.isfile(os.join(IMAGES_DIR_PATH, f))]

def main():
    """
    The main test loop: this function continues to loop through the 
    """
    images = get_images()
    
    # quit running the tests
    done = False
    
    # current position in the images list
    index = 0

    # total images scored in this test run
    images_scored = 0

    if MODE == DEFAULT_MODE:
        detector = load_detector(model_file="md_v5a.0.0.pt")

    while not done:
        # get the next image
        image_file_path = images[index]
        index += 1
        if index >= len(images):
            index = 0

        # score one image ---
        # for default mode, we use the cached detector object
        print(f"Scoring image: {image_file_path}")
        if MODE == DEFAULT_MODE:
            results= run_detector(detector=detector,
                                image_file_names=[image_file_path],
                                output_dir=OUTPUT_DIR_PATH,
                                render_confidence_threshold=0.1,
                                box_thickness=DEFAULT_BOX_THICKNESS,
                                box_expansion=DEFAULT_BOX_EXPANSION,                          
                                crop_images=CROP_IMAGE,
                                image_size=IMAGE_SIZE)
        # otherwise, we use the old load_and_run function which loads the model every time
        else:
            results= load_and_run_detector(model_file="md_v5a.0.0.pt",
                                        image_file_names=[image_file_path],
                                        output_dir=OUTPUT_DIR_PATH,
                                        render_confidence_threshold=0.1,
                                        box_thickness=DEFAULT_BOX_THICKNESS,
                                        box_expansion=DEFAULT_BOX_EXPANSION,                          
                                        crop_images=CROP_IMAGE,
                                        image_size=IMAGE_SIZE)
        images_scored += 1

        if images_scored % 3 == 0:
            print(f"\n\n\n* * * TEST SUITE HAS SCORED {images_scored} IMAGES * * *\n\n\n")

        if images_scored >= MAX_IMAGES_TO_SCORE:
            done = True
            break

        # optionally sleep a pre-configured amount of time between scores
        time.sleep(SLEEP_TIME_PER_IMAGE)
    
    # report results
    print("\n\n* * * * * TEST SUITE COMPLETED SUCCESSFULLY * * * * * ")
    print(f"Total number of images scored: {images_scored}\n\n")


if __name__ == "__main__":
    main()

        








