# Building and Running the Integration Test

The integration test described here simply injects images into an instance of the camera-traps application configured for testing with internal plugins (only one process is started).  The application runs in a docker container whereas the integration test is invoked by cargo.  To allow the test to communicate with the application, the latter runs on the host network rather than a private docker network.  Though unlikely, failures are possible if the configured ports are already in use.

*The integration test executable must exist in order for cargo to invoke it. This typically requires a Rust development environment to run and, if necessary, build the test program.*


## Commands

The integration test requires the camera-traps application to be running before it is manually invoked.  All commands should be issued from the directory in which this file resides.     

To run an instance of camera-traps configured for the integration test, issue this command in a command-line terminal:

  *docker-compose up*

To run the integration test, issue:

  *./runtest.sh*

To shutdown the camera-traps application, issue:

  *docker-compose down*

## Output

When started in a terminal, the application will log to standard output an indication that these four internal plugins have been loaded:

- image_recv_plugin
- image_score_plugin
- image_store_plugin
- observer_plugin

The application will also indicate that an external plugin port was opened:

- ext_image_gen_test_plugin

Other informational records are also written when the application starts.  When *runtest.sh* executes, it will read the traps-integration.toml file to configure itself. That file includes the following information.

- The number of total number of times an image is injected into camera-traps (*iterations*).
- The directory where at least one image file can be found (*image_input_dir*).
- The external plugin configuration (*external_plugin_config*).

Test execution will cause four events to be logged by the observer plugin for each image received.  These events are:

- NewImageEvent
- ImageReceivedEvent
- ImageScoredEvent
- ImageStoredEvent

The level of logging detail can be controlled by modifying the log4rs.yml file in this directory.
