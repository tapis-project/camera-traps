# camera-traps

The camera-traps application is both a simulator and an edge device application for classifying images, with the first deployment specializing in wildlife images.  The simulation environment will be implemented first and serve as a test bed for protocols and techniques that optimize storage, execution time, power and accuracy.  The ultimate goal is to deploy a version of this application on camera-trap devices in the wild.

## Architectual Overview

This application uses the [event-engine](https://github.com/tapis-project/event-engine) library to implement its plugin architecture and event-driven communication.  The engine uses [zmq](https://zeromq.org/) sockets to deliver events between senders and the subscribers interested in specific events.  

The event-engine supports *internal* and *external* plugins.  Internal plugins are Rust plugins delivered with camera-traps and run in the camera-traps process.  External plugins are configured by camera-traps to run outside the camera-traps process and use a TCP port to send and receive events.  By using TCP, external plugins can be written in any language that supports the [flatbuffers](https://google.github.io/flatbuffers/) wire protocol.

## Application Configuation 

The camera-traps application requires that a configuration file be specified using an environment variable, command line parameter or accepting the default file path.  In addition, internal plugins and test programs may also require configuration files. 


| **Target**                | **Environment  Variable**     | **Default  File**        | **Notes**                             |
|---------------------------|-------------------------------|--------------------------|---------------------------------------|
| camera-traps application  | TRAPS_CONFIG_FILE             | ~/traps.toml             | Can be 1st command line parameter     |
| image_store_plugin        | TRAPS_IMAGE_STORE_FILE        | ~/traps-image-store.toml |                                       |
| integration tests         | TRAPS_INTEGRATION_CONFIG_FILE | ~/traps-integration.toml |                                       |
| logger                    | TRAPS_LOG4RS_CONFIG_FILE      | resources/log4rs.yml     | Packaged with application             |

The camera-traps application uses [log4rs](https://docs.rs/log4rs/latest/log4rs/) as its log manager.  The log settings in resources/log4rs.yml source code will be used unless overridden by assigning a log4rs.yml configuration filepath to the TRAPS_LOG4RS_CONFIG_FILE environment variable.

## Plugin Configuration

Camera-traps uses a [TOML](https://toml.io/en/) file to configure the internal and external plugins it loads.  Internal plugins are registered with the event-engine by simply specfying their names since their runtime characteristics are compiled into the application.  External plugins, on the other hand, require more detailed information in order to be registered.  Here is the example resources/traps.toml file content:

    # This is the camera-traps application configuration file.
    title = "Camera-Traps Application Configuration"

    # The event engine's publish and subscribe port used to create the event_engine::App instance.
    publish_port = 5559
    subscribe_port = 5560

    # An absolute path to the image directory is required but a file name prefix is optional.  
    # If present the prefix is preprended to generated image file names.
    images_dir = "~/camera-traps/images"
    # image_file_prefix = ""

    # The container for both internal and external plugins.  Internal plugins are written in rust 
    # and compiled into the camera-traps application.  External plugins are usually written in 
    # python but can be written in any language.  External plugins run in their own processes
    # and communicate via tcp or ipc.
    [plugins]
    # Uncomment the internal plugins loaded when the camera-traps application starts.
    internal = [
    #   "image_gen_plugin",
        "image_recv_plugin",
    #   "image_score_plugin",
        "image_store_plugin",
    #   "observer_plugin"
    ]

    # Configure each of the active internal plugins with the image processing action they should 
    # take when new work is received.  If no action is specified for a plugin, its no-op action 
    # is used by default. 
    internal_actions = [
        "image_recv_write_file_action",
        "image_store_file_action"
    ]

    # External plugins require more configuration information than internal plugins.
    # Each plugin must subscribe to PluginTerminateEvent.  
    # 
    # The ext_image_gen_test_plugin is configured to allow the Rust integration_tests.rs
    # program to run.  The ext_image_score_plugin is an example of how an external scoring
    # plugin could be configured. 
    [[plugins.external]]
        plugin_name = "ext_image_gen_test_plugin"
        id = "d3266646-41ec-11ed-a96f-5391348bab46"
        external_port = 6000
        subscriptions = [
            "PluginTerminateEvent"
        ]
    #[[plugins.external]]
    #    plugin_name = "ext_image_score_plugin"
    #    id = "d6e8e42a-41ec-11ed-a36f-a3dcc1cc761a"
    #    external_port = 6001
    #    subscriptions = [
    #        "ImageReceivedEvent",
    #        "PluginTerminateEvent"
    #    ]


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


## Using Flatbuffers

In-memory representations of events are translated into flatbuffer binary streams plus a leading two byte sequence that identifies the event type.  These statically defined byte sequences are specified in the [events.rs](https://github.com/tapis-project/camera-traps/blob/main/src/events.rs) source file and repeated here for convenience.

    // Each event is assigned a binary prefix that zqm uses to route incoming
    // binary streams to all of the event's subscribers.
    pub const NEW_IMAGE_PREFIX:          [u8; 2] = [0x01, 0x00];
    pub const IMAGE_RECEIVED_PREFIX:     [u8; 2] = [0x02, 0x00];
    pub const IMAGE_SCORED_PREFIX:       [u8; 2] = [0x03, 0x00];
    pub const IMAGE_STORED_PREFIX:       [u8; 2] = [0x04, 0x00];
    pub const IMAGE_DELETED_PREFIX:      [u8; 2] = [0x05, 0x00];
    pub const PLUGIN_STARTED_PREFIX:     [u8; 2] = [0x10, 0x00];
    pub const PLUGIN_TERMINATING_PREFIX: [u8; 2] = [0x11, 0x00];
    pub const PLUGIN_TERMINATE_PREFIX:   [u8; 2] = [0x12, 0x00];

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
