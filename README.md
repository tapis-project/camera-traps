# camera-traps

The camera-traps application is both a simulator and an edge device application for classifying images, with the first deployment specializing in wildlife images.  The simulation environment will be implemented first and serve as a test bed for protocols and techniques that optimize storage, execution time, power and accuracy.  The ultimate goal is to deploy a version of this application on camera-trap devices in the wild.

## Architectual Overview

This application uses the [event-engine](https://github.com/tapis-project/event-engine) library to implement its plugin architecture and event-driven communication.  The engine uses [zmq](https://zeromq.org/) sockets to deliver events between senders and the subscribers interested in specific events.

The event-engine supports *internal* and *external* plugins.  Internal plugins are Rust plugins delivered with camera-traps and run in the camera-traps process.  External plugins are configured by camera-traps to run outside the camera-traps process and use a TCP port to send and receive events.  By using TCP, external plugins can be written in any language that supports the [flatbuffers](https://google.github.io/flatbuffers/) wire protocol.

## Quick Start

To quickly start the application under [Docker](https://docs.docker.com/get-docker/) using docker-compose, follow these steps:

1. cd releases
2. Follow the directions in the README.md file

## Application Configuration

The camera-traps application requires configuration through environment variables or configuration files.  When launching the application from a *releases* subdirectory, the specific release's *config* directory will contain the default configuration files for running a short simulation test.

In general, plugins can also depend on their own environment variables and/or configuration files, and the same is true of test programs.  The [releases](https://github.com/tapis-project/camera-traps/tree/main/releases) directory contains docker-compose files that use default configurations, which can serve as a template for production environment configuration.


| **Target**               | **Environment  Variable**     | **Default  File**        | **Notes**                         |
| -------------------------- | ------------------------------- | -------------------------- | ----------------------------------- |
| camera-traps application | TRAPS_CONFIG_FILE             | ~/traps.toml             | Can be 1st command line parameter |
| image_gen_plugin         |                               | /input.json              |                                   |
| image_store_plugin       | TRAPS_IMAGE_STORE_FILE        | ~/traps-image-store.toml |                                   |
| power_measure_plugin     | TRAPS_POWER_LOG_PATH          | ~/logs                   |                                   |
| oracle_monitor_plugin    | TRAPS_ORACLE_OUTPUT_PATH      | ~/output                 |                                   |
| integration tests        | TRAPS_INTEGRATION_CONFIG_FILE | ~/traps-integration.toml |                                   |
| logger                   | TRAPS_LOG4RS_CONFIG_FILE      | resources/log4rs.yml     | Packaged with application         |

The external python plugins run in their own processes and do not currently use environment variables.

The camera-traps application uses [log4rs](https://docs.rs/log4rs/latest/log4rs/) as its log manager.  The log settings in [resources/log4rs.yml](https://github.com/tapis-project/camera-traps/blob/main/resources/log4rs.yml) source code will be used unless overridden by assigning a log4rs.yml configuration filepath to the TRAPS_LOG4RS_CONFIG_FILE environment variable.  To maximize logging, set root level to *trace* in the effective log4rs.yml file.  Also, include the *observer_plugin* in the internal plugins list in the effective traps.toml file.

## Plugin Configuration

Camera-traps uses a [TOML](https://toml.io/en/) file to configure the internal and external plugins it loads.  Internal plugins are registered with the event-engine by simply specfying their names since their runtime characteristics are compiled into the application.  External plugins, on the other hand, require more detailed information in order to be registered.  Here is the example resources/traps.toml file content:

> \# This is the camera-traps application configuration file for versions 0.x.y of the application.<br>
> \# It assumes the use of containers and docker-compose as the deployment mechanism.<br>
> title = "Camera-Traps Application Configuration v0.3.2"<br>
>
> \# The event engine's publish and subscribe port used to create the event_engine::App instance.<br>
> publish_port = 5559
> subscribe_port = 5560
>
> \# An absolute path to the image directory is required but a file name prefix is optional.<br>
> \# If present the prefix is preprended to generated image file names.  This is the directory<br>
> \# into which the image_recv_plugin writes incoming images and the image_store_plugin may<br>
> \# delete images or output the scores for images.<br>
> images_output_dir = "/root/camera-traps/images"<br>
> \# image_file_prefix = ""
>
> \# The container for both internal and external plugins.  Internal plugins are written in rust<br>
> \# and compiled into the camera-traps application.  External plugins are usually written in<br>
> \# python but can be written in any language.  External plugins run in their own processes<br>
> \# and communicate via tcp or ipc.<br>
> [plugins]
> \# Uncomment the internal plugins loaded when the camera-traps application starts.<br>
> internal = [<br>
> \#    "image_gen_plugin",<br>
> "image_recv_plugin",<br>
> \#    "image_score_plugin",<br>
> "image_store_plugin",<br>
> \#    "observer_plugin"<br>
> ]
>
> \# Configure each of the active internal plugins with the image processing action they should<br>
> \# take when new work is received.  If no action is specified for a plugin, its no-op action<br>
> \# is used by default.<br>
> internal_actions = [<br>
> "image_recv_write_file_action",<br>
> "image_store_file_action"<br>
> ]
>
> \# External plugins require more configuration information than internal plugins.<br>
> \# Each plugin must subscribe to PluginTerminateEvent.<br>
> \# <br>
> \# Note that each plugin must specify the external port to use in TWO PLACES: here as well as<br>
> \# in the docker-compose.yml file. If external_port changes here, it must ALSO be changed in the<br>
> \# docker-compose.yml file.<br>
> [[plugins.external]]<br>
> plugin_name = "ext_image_gen_plugin"<br>
> id = "d3266646-41ec-11ed-a96f-5391348bab46"<br>
> external_port = 6000<br>
> subscriptions = [<br>
> "PluginTerminateEvent"<br>
> ]<br>
> [[plugins.external]]<br>
> plugin_name = "ext_image_score_plugin"<br>
> id = "d6e8e42a-41ec-11ed-a36f-a3dcc1cc761a"<br>
> external_port = 6001<br>
> subscriptions = [<br>
> "ImageReceivedEvent",<br>
> "PluginTerminateEvent"<br>
> ]<br>
> [[plugins.external]]<br>
> plugin_name = "ext_power_monitor_plugin"<br>
> id = "4a0fca25-1935-472a-8674-58f22c3a32b3"<br>
> external_port = 6010<br>
> subscriptions = [<br>
> "MonitorPowerStartEvent",<br>
> "MonitorPowerStopEvent",<br>
> "PluginTerminateEvent"<br>
> ]<br>
> [[plugins.external]]<br>
> plugin_name = "ext_power_control_plugin"<br>
> id = "a59621f2-4db6-4892-bda1-59ecb7ff24ae"<br>
> external_port = 6011<br>
> subscriptions = [<br>
> "PluginTerminateEvent"<br>
> ]<br>
> [[plugins.external]]<br>
>   plugin_name = "ext_oracle_monitor_plugin"<br>
>   id = "6e153711-9823-4ee6-b608-58e2e801db51"<br>
>  external_port = 6011<br>
> subscriptions = [<br>
>       "ImageScoredEvent",<br>
>       "ImageStoredEvent",<br>
>       "ImageDeletedEvent",<br>
>       "PluginTerminateEvent"<br>
>   ]<br>
>
>


Every plugin must subscribe to the PluginTerminateEvent, which upon receipt causes the plugin to stop.  Subscriptions are statically defined in internal plugin code and explicitly configured for external plugins.  External plugins also provide their predetermined UUIDs and external TCP ports.

Camera-traps looks for its configuration file using these methods in the order shown:

1. The environment variable $TRAPS_CONFIG_FILE.
2. The first command line argument.
3. $HOME/traps.toml

The first file it finds it uses.  If no configuration file is found the program aborts.

### Internal Plugin Configuration

The names listed in the *internal* list are the rust plugin file names.  These plugins run as separate threads in the camera-traps process.  The *internal_actions* list contains the file names that implement the different algorithms or actions associated with each internal plugin.

A naming convention is used to associate actions with their plugins:  An action name starts with its plugin name minus the trailing "plugin" part, followed by an action identifier part, and ends with "_action".  Each plugin has a no-op action that causes it to take no action other than, possibly, generating the next event in the pipeline.  For example, *image_gen_noop_action* is associated with the *image_gen_plugin*.

Internal plugins for which no corresponding action is specified are assigned their no-op plugin by default.

### image_recv_plugin

When *image_recv_write_file_action* is specifed, the *image_recv_plugin* uses the *image_dir* and *image_file_prefix* parameters to manage files.  The image_dir is the directory into which image files are placed.  Image file names are constructed from the information received in a NewImageEvent and have this format:

<image_file_prefix><image_uuid>.<image_format>
The *image_uuid* and *image_format* are from the NewImageEvent.  The image_file_prefix can be the empty string and the image_format is always lowercased when used in the file name.

## Support for NVIDIA
The Image Scoring plugin can make use of NVIDIA GPUs to improve the performance of object detection and classification with some ML models. In order to make use of NVIDIA GPUs in the Camera Traps application, the following steps must be taken:

1. *Ensure the NVIDIA drivers are installed natively on the machine*. For example, on Ubuntu LTS, follow the instructions in Section 3.1 [here](https://docs.nvidia.com/datacenter/tesla/tesla-installation-notes/index.html). Be sure to reboot your machine after adding the keyring and installing the drivers. You can check to see if the drivers are installed properly and communicating with the hardware by running the following command: 

```
nvidia-smi
```

2. *Install the NVIDIA Container Toolkit and configure the Docker Runtime*. See the instructions [here](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). Make sure to restart Docker after installing and configuring the toolkit. To check if the toolkit and Docker are installed and configured correctly, run the following:

```
docker run --gpus=all --rm -it ubuntu nvidia-smi
```
The output should be similar to the output from Step 1.

3. *Update the Camera Traps Compose File to Use GPUs*. Starting with release 0.3.3, the official Camera Traps releases docker-compose files include stanzas for making NVIDIA GPUs available to 
both the Image Scoring and Power Monitoring plugins. At this time, those stanzas must be 
uncommented; see the [docker-compose.yml](releases/0.3.3/docker-compose.yml) file for more details.


## Support for ARM CPUs

*This section is a work in progress...*

We are currently working on support for ARM CPUs, including support for Mac OSX M* hardware. 



# Developer Information

## Using Flatbuffers

In-memory representations of events are translated into flatbuffer binary streams plus a leading two byte sequence that identifies the event type.  These statically defined byte sequences are specified in the [events.rs](https://github.com/tapis-project/camera-traps/blob/main/src/events.rs) source file and repeated here for convenience.

// Each event is assigned a binary prefix that zqm uses to route incoming binary streams to all of the event's subscribers.<br>
pub const NEW_IMAGE_PREFIX:           [u8; 2] = [0x01, 0x00];<br>
pub const IMAGE_RECEIVED_PREFIX:      [u8; 2] = [0x02, 0x00];<br>
pub const IMAGE_SCORED_PREFIX:        [u8; 2] = [0x03, 0x00];<br>
pub const IMAGE_STORED_PREFIX:        [u8; 2] = [0x04, 0x00];<br>
pub const IMAGE_DELETED_PREFIX:       [u8; 2] = [0x05, 0x00];<br>
pub const PLUGIN_STARTED_PREFIX:      [u8; 2] = [0x10, 0x00];<br>
pub const PLUGIN_TERMINATING_PREFIX:  [u8; 2] = [0x11, 0x00];<br>
pub const PLUGIN_TERMINATE_PREFIX:    [u8; 2] = [0x12, 0x00];<br>
pub const MONITOR_POWER_START_PREFIX: [u8; 2] = [0x20, 0x00];<br>
pub const MONITOR_POWER_STOP_PREFIX:  [u8; 2] = [0x21, 0x00];<br>

Each event sent or received begins with its two byte prefix followed by its serialized form as defined in the camera-traps flatbuffer definition file ([events.fbs](https://github.com/tapis-project/camera-traps/blob/main/resources/events.fbs)).  The following section describes how to generate Rust source code from this definition file, a similar process can be used for any language supported by flatbuffers.

## Updating the flatbuffers messages

Flatbuffers info: https://google.github.io/flatbuffers/

The flatbuffers messages schema is defined in the `resources/events.fsb` file. To change the message formats do the following:

1. Edit the `resources/events.fsb` file with your changes.
2. From the camera-traps directory, regenerate the `events_generated.rs` code with the command:

```
$ flatc --rust -o src resources/events.fbs
```

3. (Optional) Add the following line to the top of the `src/events_generated.rs` file so that clippy warnings are suppressed:

```
// this line added to keep clippy happy
#![allow(clippy::all)]
```

## Plugin Start and Stop Protocol

Each plugin is required to conform to the following conventions:

1. Register for the *PluginTerminateEvent*.
2. Send a *PluginStartedEvent* when it begins executing.
3. Send a *PluginTerminatingEvent* when it shuts down.

The *PluginStartedEvent* advertises a plugin's name and uuid when it starts.  When a plugin receives a *PluginTerminateEvent*, it checks if the event's *target_plugin_name* matches its name or the wildcard name (*).  If either is true, then the plugin is expected to gracefully terminate.  The plugin is also expected to gracefully terminate if the event's *target_plugin_uuid* matches the plugin's uuid.  Part of plugin termination is for it to send a *PluginTerminatingEvent* to advertise that it's shutting down, whether in response to a *PluginTerminateEvent* or for any other reason.

## Building and Running under Docker

The instructions in this section assume [Docker](https://docs.docker.com/get-docker/) (and docker-compose) are installed, as well as [Rust](https://www.rust-lang.org/tools/install), [cargo](https://doc.rust-lang.org/cargo/getting-started/installation.html) and make.

From the top-level camera-traps directory, issue the following command to build the application's Docker images:

make build
See [Makefile](https://github.com/tapis-project/camera-traps/blob/main/Makefile) for details.  From the [releases](https://github.com/tapis-project/camera-traps/tree/main/releases) directory, navigate to the subdirectory of the specific release you want to run.  Issue the following command to run the application, including the external plugins for which it's configured:

docker-compose up
See [docker-compose.yaml](https://github.com/tapis-project/camera-traps/blob/main/releases/0.3.2/docker-compose.yml) for details.  From the same release directory, issue the following command to stop the application:

docker-compose down

## Building and Running the Rust Code

If you're just interested in building the Rust, issue *cargo build* from the top-level camera-traps directory.  Alternatively, issue *cargo run* to build and run it.  External plugins are not started using this approach.  The internal plugins and their actions are configured using a *traps.toml* file, as discussed above.

## Integration Testing

The camera-traps/tests directory contains [integration_tests.rs](https://github.com/tapis-project/camera-traps/blob/main/tests/integration_tests.rs) program.  The integration test program runs as an external plugin configured via a *traps.toml* file as shown above.  See the top-level comments in the source code for details.

## Plugin Development

This section addresses two questions:

- Why would I want to create a plugin?
- What kind of plugin should I create?



One would want to create their own plugin if they wanted to read or write events and perform some new action that isn't currently implemented.  If an existing plugin doesn't do what you want, you have the option of modifying that plugin or creating another plugin that acts on the same events and does what you need.

For example, the *image_gen_plugin* injects new images into the event stream, the *image_recv_plugin* writes new images to file, etc.  The *observer_plugin* is one that subscribes to all events and logs them for debugging purposes.  Most of the time we don't run the *observer_plugin*, but if we want extended logging we just include it to run in the traps.toml file.  In this case, having a separate plugin from which we can customize the logging of all events is more convenient then adding that logging capability to each existing plugin.

Another reason for introducing a new plugin would be to also service new events.  As the application evolves new capabilities might require new events.  This occurred as we develop support for power monitoring, which introduces 2 new events and a plugin to handle them.

When implementing a plugin the choice between internal and external is often technology driven.  Do we want to write a plugin in Rust and compile it into the application (internal) or do we want to write it in some other language and start it up in its own container (external)?  Considerations as to which approach to take include performance, resource usage, and availability of domain-specific libraries.

## Release Procedures

When development on a new release begins a launch configuration is created in the new release's own [releases](https://github.com/tapis-project/camera-traps/tree/main/releases) subdirectory.  When development completes and the final version of the release's images are pushed to docker hub, we tag those images with the release number and with the "latest" tag.

To be able to rebuild a release at anytime, we also tag the release's source code in github.  The tag is the same as the release version number.  Once confident that the tagged code is stable, release tags can be protected using github [tag protection](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/configuring-tag-protection-rules).

# Acknowledgements

*This work has been funded by grants from the National Science Foundation, including the ICICLE AI Institute (OAC 2112606) and Tapis (OAC 1931439).*
