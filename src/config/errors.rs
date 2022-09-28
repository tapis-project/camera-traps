use thiserror::Error;

/// Error enumerates the errors returned by this application.
#[derive(Error, Debug)]
pub enum Errors {
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

    #[error("Plugin {0} received event with mismatched prefix ({1} and type ({2}).)")]
    EventPrefixMismatch(String, String, String),

    #[error("Plugin {0} is processing event type {1}.")]
    EventProcessing(String, &'static str),

    #[error("Unable to read buffer for field {}.", .0)]
    EventReadFlatbuffer(String),

    #[error("Unable to read event from subscription socket: {}", .0)]
    EventReadError(String),

    #[error("Unable to read event type from raw event, expected type is: {}", .0)]
    EventReadTypeError(String),

    #[error("Plugin {} is unable to send a {} event: {}", .0, .1, .2)]
    EventSendError(String, String, String),

    #[error("Plugin {} is unable to convert a {} event to vector of bytes: {}", .0, .1, .2)]
    EventToBytesError(String, String, String),

    #[error("Expected event type {}, but received event {} instead.", .0, .1)]
    EventUnexpectedError(String, String),

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

    #[error("\n**** Plugin {} ({}) starting execution.", .0, .1)]
    PluginStarted(String, String),

    #[error("Plugin {0} ({1})registered with event-engine.")]
    PluginRegistered(String, String),

    #[error("Unknown plugin {0} could not be registered, aborting application.")]
    PluginUnknown(String),

    #[error("Reading application configuration file: {}", .0)]
    ReadingConfigFile(String),

    #[error("Plugin {0} failed to read a byte stream from its subscription socket: {1}")]
    SocketRecvError(String, String),

    #[error("Plugin {} is unable to send a {} event: {}", .0, .1, .2)]
    SocketSendError(String, String, String),

    #[error("Unable to parse TOML file: {}", .0)]
    TOMLParseError(String),

    #[error("Unable to parse string '{}' into a Uuid: {}", .0, .1)]
    UUIDParseError(String, String),
}