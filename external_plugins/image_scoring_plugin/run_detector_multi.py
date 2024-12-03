import glob
import os
import statistics
import time
from tqdm import tqdm
import humanfriendly
import logging
import visualization_utils as viz_utils

log_level = os.environ.get("IMAGE_SCORING_LOG_LEVEL", "INFO")
logger = logging.getLogger("Image Scoring Plugin")
if log_level == "DEBUG":
    logger.setLevel(logging.DEBUG)
elif log_level == "INFO":
    logger.setLevel(logging.INFO)
elif log_level == "WARN":
    logger.setLevel(logging.WARN)
elif log_level == "ERROR":
    logger.setLevel(logging.ERROR)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

DETECTOR_METADATA = {
    'v5a.0.0':
        {'megadetector_version':'v5a.0.0',
         'typical_detection_threshold':0.2,
         'conservative_detection_threshold':0.05},
    'v5b.0.0':
        {'megadetector_version':'v5b.0.0',
         'typical_detection_threshold':0.2,
         'conservative_detection_threshold':0.05}
}


DEFAULT_RENDERING_CONFIDENCE_THRESHOLD = DETECTOR_METADATA['v5b.0.0']['typical_detection_threshold']
DEFAULT_OUTPUT_CONFIDENCE_THRESHOLD = 0.005

DEFAULT_BOX_THICKNESS = 4
DEFAULT_BOX_EXPANSION = 0

# Label mapping for MegaDetector
model_variant = os.environ.get('MODEL_TYPE', '0')
if model_variant == "2":
# Label mapping for MegaDetector
    DEFAULT_DETECTOR_LABEL_MAP = {
        "1": "bird",
        "2": "eastern gray squirrel",
        "3": "eastern chipmunk",
        "4": "woodchuck",
        "5": "wild turkey",
        "6": "white-tailed deer",
        "7": "virginia opossum",
        "8": "eastern cottontail",
        "9": "empty",
        "10": "vehicle",
        "11": "striped skunk",
        "12": "red fox",
        "13": "eastern fox squirrel",
        "14": "northern raccoon",
        "15": "grey fox",
        "16": "horse",
        "17": "dog",
        "18": "american crow",
        "19": "chicken",
        "20": "domestic cat",
        "21": "coyote",
        "22": "bobcat",
        "23": "american black bear",
        # available in megadetector v4+
    }
else:
    DEFAULT_DETECTOR_LABEL_MAP = {
        '1': 'animal',
        '2': 'person',
        '3': 'vehicle',
        '4': 'empty',
        # available in megadetector v4+
    }
    

FAILURE_IMAGE_OPEN = 'Failure image access'


class ImagePathUtils:
    """A collection of utility functions supporting this stand-alone script"""

    # Stick this into filenames before the extension for the rendered result
    DETECTION_FILENAME_INSERT = '_detections'

    image_extensions = ['.jpg', '.jpeg', '.gif', '.png']

    @staticmethod
    def is_image_file(s):
        """
        Check a file's extension against a hard-coded set of image file extensions
        """
        ext = os.path.splitext(s)[1]
        return ext.lower() in ImagePathUtils.image_extensions

    @staticmethod
    def find_image_files(strings):
        """
        Given a list of strings that are potentially image file names, look for strings
        that actually look like image file names (based on extension).
        """
        return [s for s in strings if ImagePathUtils.is_image_file(s)]

    @staticmethod
    def find_images(dir_name, recursive=False):
        """
        Find all files in a directory that look like image file names
        """
        if recursive:
            strings = glob.glob(os.path.join(dir_name, '**', '*.*'), recursive=True)
        else:
            strings = glob.glob(os.path.join(dir_name, '*.*'))

        image_strings = ImagePathUtils.find_image_files(strings)

        return image_strings


#%% Utility functions


def is_gpu_available(model_file):
    """Decide whether a GPU is available, importing PyTorch or TF depending on the extension
    of model_file.  Does not actually load model_file, just uses that to determine how to check 
    for GPU availability."""
    
    if model_file.endswith('.pb'):
        import tensorflow.compat.v1 as tf
        gpu_available = tf.test.is_gpu_available()
        print('TensorFlow version:', tf.__version__)
        print('tf.test.is_gpu_available:', gpu_available)                
        return gpu_available
    elif model_file.endswith('.pt'):
        import torch
        gpu_available = torch.cuda.is_available()
        print('PyTorch reports {} available CUDA devices'.format(torch.cuda.device_count()))
        if not gpu_available:
            try:
                # mps backend only available in torch >= 1.12.0
                if torch.backends.mps.is_built and torch.backends.mps.is_available():
                    gpu_available = True
                    print('PyTorch reports Metal Performance Shaders are available')
            except AttributeError:
                pass
        return gpu_available
    else:
        raise ValueError('Unrecognized model file extension for model {}'.format(model_file))


def load_detector(model_file, force_cpu=False):
    """Load a TF or PT detector, depending on the extension of model_file."""
    
    start_time = time.time()
    if model_file.endswith('.pb'):
        from tf_detector import TFDetector
        if force_cpu:
            raise ValueError('force_cpu option is not currently supported for TF detectors, use CUDA_VISIBLE_DEVICES=-1')
        detector = TFDetector(model_file)
    elif model_file.endswith('.pt'):
        from pytorch_detector import PTDetector
        detector = PTDetector(model_file, force_cpu)
    else:
        raise ValueError('Unrecognized model format: {}'.format(model_file))
    elapsed = time.time() - start_time
    print('Loaded model in {}'.format(humanfriendly.format_timespan(elapsed)))
    return detector


def run_detector(detector, image_file_names, output_dir,
                 render_confidence_threshold=DEFAULT_RENDERING_CONFIDENCE_THRESHOLD,
                 crop_images=False, detections = False, box_thickness=DEFAULT_BOX_THICKNESS, 
                 box_expansion=DEFAULT_BOX_EXPANSION, image_size=None
                 ):
    """
    Apply the detector to an image. Requires the `detector` object to have been loaded already.
    """
    detection_results = []
    time_load = []
    time_infer = []

    # Dictionary mapping output file names to a collision-avoidance count.
    #
    # Since we'll be writing a bunch of files to the same folder, we rename
    # as necessary to avoid collisions.
    output_filename_collision_counts = {}

    def input_file_to_detection_file(fn, crop_index=-1):
        """Creates unique file names for output files.

        This function does 3 things:
        1) If the --crop flag is used, then each input image may produce several output
            crops. For example, if foo.jpg has 3 detections, then this function should
            get called 3 times, with crop_index taking on 0, 1, then 2. Each time, this
            function appends crop_index to the filename, resulting in
                foo_crop00_detections.jpg
                foo_crop01_detections.jpg
                foo_crop02_detections.jpg

        2) If the --recursive flag is used, then the same file (base)name may appear
            multiple times. However, we output into a single flat folder. To avoid
            filename collisions, we prepend an integer prefix to duplicate filenames:
                foo_crop00_detections.jpg
                0000_foo_crop00_detections.jpg
                0001_foo_crop00_detections.jpg

        3) Prepends the output directory:
                out_dir/foo_crop00_detections.jpg

        Args:
            fn: str, filename
            crop_index: int, crop number

        Returns: output file path
        """
        fn = os.path.basename(fn).lower()
        name, ext = os.path.splitext(fn)
        if crop_index >= 0:
            name += '_crop{:0>2d}'.format(crop_index)
        fn = '{}{}{}'.format(name, ImagePathUtils.DETECTION_FILENAME_INSERT, '.jpg')
        if fn in output_filename_collision_counts:
            n_collisions = output_filename_collision_counts[fn]
            fn = '{:0>4d}'.format(n_collisions) + '_' + fn
            output_filename_collision_counts[fn] += 1
        else:
            output_filename_collision_counts[fn] = 0
        fn = os.path.join(output_dir, fn)
        return fn

    # ...def input_file_to_detection_file()
    
    for im_file in tqdm(image_file_names):

        try:
            start_time = time.time()

            image = viz_utils.load_image(im_file)

            elapsed = time.time() - start_time
            time_load.append(elapsed)

        except Exception as e:
            print('Image {} cannot be loaded. Exception: {}'.format(im_file, e))
            result = {
                'file': im_file,
                'failure': FAILURE_IMAGE_OPEN
            }
            detection_results.append(result)
            continue

        try:
            start_time = time.time()

            result = detector.generate_detections_one_image(image, im_file,
                                                            detection_threshold=DEFAULT_OUTPUT_CONFIDENCE_THRESHOLD,
                                                            image_size=image_size)
            detection_results.append(result)

            elapsed = time.time() - start_time
            time_infer.append(elapsed)

        except Exception as e:
            print('An error occurred while running the detector on image {}. Exception: {}'.format(im_file, e))
            continue

        try:
            if crop_images:
                logger.info(f"Cropping the image - {image_file_names}")
                images_cropped = viz_utils.crop_image(result['detections'], image)
                
                for i_crop, cropped_image in enumerate(images_cropped):
                    output_full_path = input_file_to_detection_file(im_file, i_crop)
                    cropped_image.save(output_full_path)

            if detections:
                logger.info(f"Performing detections on image - {image_file_names}")

                # Image is modified in place
                viz_utils.render_detection_bounding_boxes(result['detections'], image,
                                                          label_map=DEFAULT_DETECTOR_LABEL_MAP,
                                                          confidence_threshold=render_confidence_threshold,
                                                          thickness=box_thickness, expansion=box_expansion)
                output_full_path = input_file_to_detection_file(im_file)
                image.save(output_full_path)

        except Exception as e:
            print('Visualizing results on the image {} failed. Exception: {}'.format(im_file, e))
            continue

    # ...for each image

    ave_time_load = statistics.mean(time_load)
    ave_time_infer = statistics.mean(time_infer)
    if len(time_load) > 1 and len(time_infer) > 1:
        std_dev_time_load = humanfriendly.format_timespan(statistics.stdev(time_load))
        std_dev_time_infer = humanfriendly.format_timespan(statistics.stdev(time_infer))
    else:
        std_dev_time_load = 'not available'
        std_dev_time_infer = 'not available'
    print('On average, for each image,')
    print('- loading took {}, std dev is {}'.format(humanfriendly.format_timespan(ave_time_load),
                                                    std_dev_time_load))
    print('- inference took {}, std dev is {}'.format(humanfriendly.format_timespan(ave_time_infer),
                                                      std_dev_time_infer))
    # print(f"{result['max_detection_conf']} {type(result['max_detection_conf'])}")
    if not result['detections'] and model_variant != "2":
        result['detections'].append({'category':'4', 'conf': 0})
    return result['detections']


def load_and_run_detector(model_file, image_file_names, output_dir,
                          render_confidence_threshold=DEFAULT_RENDERING_CONFIDENCE_THRESHOLD,
                          crop_images=False, detections = False,box_thickness=DEFAULT_BOX_THICKNESS, 
                          box_expansion=DEFAULT_BOX_EXPANSION, image_size=None
                          ):
    """Load and run detector on target images, and visualize the results."""
    
    if len(image_file_names) == 0:
        print('Warning: no files available')
        return

    print('GPU available: {}'.format(is_gpu_available(model_file)))
    
    detector = load_detector(model_file)
    result = run_detector(detector, image_file_names, output_dir,
                          render_confidence_threshold, crop_images, detections, box_thickness, 
                          box_expansion, image_size)
    return result    
# ...def load_and_run_detector()

