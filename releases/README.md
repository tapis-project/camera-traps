# Running Released Versions of Camera-Traps

Running the camera-traps application as described here requires docker to be installed.  Later versions of docker include docker-compose, earlier versions may require a separate installation of docker-compose.

Each of the subdirectories in this directory corresponds to a released version of the camera-traps application.  Each release has its own tagged images in docker hub.  When invoked, a release's docker-compose file will start the application and its internal plugins in one container.  It will also start all configured external plugins in their own containers.  

Typically, the external *image_generating_plugin* reads a small set of sample images from a configured directory and injects them into the application.  Successful processing of these sample images indicates that the application is functional.  The *image_generating_plugin* container terminates after reading the image directory.  One way to inject your own images into the application is to configure the *image_generating_plugin* to read from a directory containing images of your choosing.

## Common Files

Each release can have its own customized configuration files.  Here is a list of files you may encounter:

1. **docker-compose.yml** - the file that configures all containers.  It is used to bring up and tear down the application and its external plugins.
2. **config/traps.toml** - the camera-traps application configuration file that specfies the internal and external plugins that will run.
3. **config/image_gen_config.json** - configuration setting for the *image_generating_plugin*.

## Example:  Running the Latest Release

1. cd latest
2. docker-compose up

There should be no errors as the application processes each sample image.  The *image_generating_plugin* container will exit when all images are read from the configured input directory.  The output images and scores will be in the release's *images_dir* (pre 0.3.2)
*images_output_dir* (0.3.2 onward).  

To shutdown the application, issue this command from another terminal:

- docker-compose down

## Integration Tests

Some releases will include in integration test subdirectory.  These tests can be useful to developers for debugging and require a Rust development environment.  The *runtest.sh* script invokes the tests.

