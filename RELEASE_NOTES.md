# Camera Traps Release Notes

## Version 0.3.3

1. Implementation of power monitoring plugin for x86 and ARM architectures.
2. Implementation of oracle plugin to analyze simulation results.
2. Various bug fixes.

## Version 0.3.2

1. Runtime configuration updates, principally involving changes to the *releases* directory structure.
2. Improved release procedure documentation in top-level README file.

## Version 0.3.1

Interum release with Rust support for 2 new power monitoring events.

1. Removal of image_uuid field from ImageLabelScore type used in ImageScoredEvent.
2. MonitorPowerStartEvent and MonitorPowerStopEvent implemented in Rust (Python support in progress).
3. The image_store_plugin deletes files of all types associated with an image when that image is deleted.

## Version 0.3.0

Initial release of camera-traps images with the following features:

1. [Event Engine](https://github.com/tapis-project/event-engine) v0.2.0.
2. Internal Rust production plugins image_recv_plugin, image_store_plugin and observer_plugin.  The image_recv_plugin always writes the image to the configured images directory.  The image_store_plugin determines if an images, based on its score, should be kept or deleted.  If kept, its scores are written to a similarly named file with a *.score* suffix.
3. Internal Rust test plugins image_gen_plugin and image_score_plugin.  These plugins can be used when not running the cooresponding external plugins.
4. External Python production plugins image_gen_plugin and image_score_plugin. The image_gen_plugin injects serveral built-in images into the application and image_score_plugin calls the [Microsoft detector](https://github.com/microsoft/CameraTraps) with its [MegaDetector](https://github.com/microsoft/CameraTraps/blob/main/megadetector.md) model to score the images for animal content.
