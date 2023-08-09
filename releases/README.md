# Running Released Versions of Camera-Traps

Running the camera-traps application as described here requires docker to be installed.  Later versions of docker include docker-compose, earlier versions may require a separate installation of docker-compose.

Each of the subdirectories in this directory corresponds to a released or under development version of the camera-traps application.  Usually, there will be at most only one release under development, the one with the highest release number.

Each release has its own tagged images in docker hub.  When invoked, a release's docker-compose file will start the application and its internal plugins in one container.  It will also start all configured external plugins in their own containers.

By default, the external *image_generating_plugin* reads a small set of sample images from a configured directory and injects them into the application.  Successful processing of these sample images indicates that the application is functional.  The *image_generating_plugin* container terminates after reading the image directory.  One way to inject your own images into the application is to configure the *image_generating_plugin* to read from a directory containing images of your choosing.  See the *config/image_gen_config.json* for details.

## Release Files

Each release can have its own customized configuration files.  A docker-compose.yml file will always reside in the release's top-level directory; other configuration files will be in the *config* subdirectory.  Here are files you may encounter:

1. **docker-compose.yml** - the file that configures all containers.  It is used to bring up and tear down the application and its external plugins.
2. **config/traps.toml** - the camera-traps application configuration file that specfies the internal and external plugins that will run.
3. **config/image_gen_config.json** - configuration setting for the *image_generating_plugin*, including the designated input images directory.
4. **config/\<plugin-config-file>** - each plugin can have it's own toml or json configuration file.

The *releases/common* directory contains data and configuration files available to all releases.  In addition, log configuration is managed using the *resources/log4rs.yml* file.

## Example:  Running the Latest Release

1. cd latest
2. docker-compose up

There should be no errors as the application processes each sample image.  The *image_generating_plugin* container will exit when all images are read from the configured input directory.  The output images and scores will be in the release's *images_output_dir* directory.

To shutdown the application, issue this command from another terminal:

- docker-compose down

## Integration Tests

Some releases will include in integration test subdirectory.  These tests can be useful to developers for debugging and require a Rust development environment.  The *runtest.sh* script invokes the tests.

## A Note on Compilation

Even though one can run current and past releases from the *releases* directory, code compilation and image generation is tied to the code version currently checked out from the source code [repository](https://github.com/tapis-project/camera-traps).  See the top-level README file for build instructions and our development process.
