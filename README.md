# camera-traps

When complete, the camera-traps application will be both a simulator and an edge device application for classifying wildlife images.  The simulation environment will be implemented first and serve as a test bed for protocols and techniques that optimize storage, execution time, power and accuracy.  The ultimate goal is to deploy a version of this application on camera-traps in the wild. 

This crate uses the [event-engine](https://github.com/tapis-project/event-engine) library to implement its plugin architecture and event-driven communication.

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
