use thiserror::Error;

/// Error enumerates the errors returned by this application.
#[derive(Error, Debug)]
pub enum Errors {
    #[error("Unable to create an event from a buffer of type {}", .0)]
    EventCreateFromFlatbuffer(String),

    #[error("Unable to read event from subscription socket: {}", .0)]
    EventReadError(String),

    #[error("Unable to read event type from raw event, expected type is: {}", .0)]
    EventReadTypeError(String),

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

    #[error("Reading application configuration file: {}", .0)]
    ReadingConfigFile(String),

    #[error("Unable to parse TOML file: {}", .0)]
    TOMLParseError(String),
}