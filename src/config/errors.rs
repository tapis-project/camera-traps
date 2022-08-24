use thiserror::Error;

/// Error enumerates the errors returned by this application.
#[derive(Error, Debug)]
pub enum Errors {
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