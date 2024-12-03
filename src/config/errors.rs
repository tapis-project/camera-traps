use thiserror::Error;

/// Error enumerates the errors returned by this application.
#[derive(Error, Debug)]
pub enum Errors {
    #[error("Internal plugin {0} is configured with action {1}.")]
    ActionConfigured(String, String),

    #[error("Internal plugin {0} initialization failed because invalid action {1} was configured.")]
    ActionImageFormatTypeError(String, String),

    #[error("Action {1} in plugin {0} received a {2} event but could not access the image data.")]
    ActionNoImageError(String, String, String),

    #[error("Internal plugin {0} initialization failed because invalid action {1} was configured.")]
    ActionNotFound(String, String),

    #[error("Action {1} in plugin {0} failed to open file {2}: {3}")]
    ActionOpenFileError(String, String, String, String),

    #[error("Action {1} in plugin {0} failed to write file {2}: {3}")]
    ActionWriteFileError(String, String, String, String),

    #[error("Unable to create directory {0}: {1}")]
    AppDirCreateError(String, String),

    #[error("Directory {0} does not have required {1} permission: {2}")]
    AppDirPermissionError(String, String, String),

    #[error("Camera-Traps application shutting down due to error: {0}")]
    AppErrorShutdown(String),

    #[error("Camera-Traps application shutting down normally.")]
    AppNormalShutdown(),

    #[error("Unable to create an event from a buffer of type {}.", .0)]
    EventCreateFromFlatbuffer(String),

    #[error("Unable to create an event from buffer contents: {0}")]
    EventFromFlatbuffer(String),

    #[error("Plugin {0} received an ill-formed event length {0}.")]
    EventInvalidLen(String, usize),

    #[error("Plugin {0} received an unknown event type which it is ignoring.")]
    EventNoneError(String),

    #[error("Plugin {0} received event type {1} which it does not handle.")]
    EventNotHandledError(String, String),

    #[error("Plugin {0} received event with mismatched prefix ({1} and type ({2}.")]
    EventPrefixMismatch(String, String, String),

    #[error("Plugin {0} is processing event type {1}.")]
    EventProcessing(String, &'static str),

    #[error("Unable to read buffer for field {}.", .0)]
    EventReadFlatbuffer(String),

    #[error("Unable to read event from subscription socket: {}", .0)]
    EventReadError(String),

    #[error("Unable to read event type from raw event, expected type is: {}", .0)]
    EventReadTypeError(String),

    #[error("Event {0} was received with an empty {1} list.")]
    EventReceivedEmptyList(String, String),

    #[error("Plugin {} is unable to send a {} event: {}", .0, .1, .2)]
    EventSendError(String, String, String),

    #[error("Plugin {} is unable to convert a {} event to vector of bytes: {}", .0, .1, .2)]
    EventToBytesError(String, String, String),

    #[error("Plugin {} is unable to convert a {} event to vector to JSON: {}", .0, .1, .2)]
    EventToJsonError(String, String, String),

    #[error("Expected event type {}, but received event {} instead.", .0, .1)]
    EventUnexpectedError(String, String),

    #[error("Deleted file {0}")]
    FileDeleted(String),

    #[error("Failed to delete file {0}: {1}")]
    FileDeleteError(String, String),

     #[error("File IO error: {}", .0)]
    FileIOError(String),

    /// Input parameter logging.
    #[error("Camera-Traps input parameters:\n{}", .0)]
    InputParms(String),

    /// Represents all other cases of `std::io::Error`.
    #[error(transparent)]
    IOError(#[from] std::io::Error),

    /// Inaccessible logger configuration file.
    #[error("Unable to access the Log4rs configuration file: {}", .0)]
    Log4rsInitialization(String),

    #[error("Plugin {0} failed to deserialize expected {1} event.")]
    PluginEventDeserializationError(String, String),

    #[error("Plugin {0} failed when trying to access a {1} event's image_uuid.")]
    PluginEventAccessUuidError(String, String),

    #[error("Plugin {0} failed executing action on {1} event; processing aborted for image {2}.")]
    PluginEventActionError(String, String, String),

    #[error("Plugin {0} failed when trying to parse a {1} event's image_uuid: {2}")]
    PluginEventParseUuidError(String, String, String),

    #[error("\n**** Plugin {} ({}) starting execution.", .0, .1)]
    PluginStarted(String, String),

    #[error("Plugin {0} ({1}) does not subscribe to the required PluginTerminateEvent event.")]
    PluginMissingSubscription(String, String),

    #[error("No internal or external plugins are configured.")]
    PluginNone(),

    #[error("Unknown plugin {0} could not be registered, aborting application.")]
    PluginUnknown(String),

    #[error("Reading application configuration file: {}", .0)]
    ReadingConfigFile(String),

    #[error("\n  -- Registering external plugin {0} with UUID {1}, port {2}, and {3} subscriptions.")]
    RegisteringExternalPlugin(String, String, i32, usize),

    #[error("\n -- Registering internal plugin {0} with UUID {1}.")]
    RegisteringInternalPlugin(String, String),

    #[error("\nRegistering {0} external plugin(s).")]
    RegisteringNumExternalPlugins(usize),

    #[error("\nRegistering {0} internal plugin(s).")]
    RegisteringNumInternalPlugins(usize),

    #[error("Plugin {0} failed to read a byte stream from its subscription socket: {1}")]
    SocketRecvError(String, String),

    #[error("Plugin {} is unable to send a {} event: {}", .0, .1, .2)]
    SocketSendError(String, String, String),

    #[error("Unable to parse string '{}' into a Date: {}", .0, .1)]
    DateParseError(String, String),

    #[error("Unable to parse TOML file: {}", .0)]
    TOMLParseError(String),

    #[error("Unable to parse string '{}' into a Uuid: {}", .0, .1)]
    UUIDParseError(String, String),
}