// Stardard imports.
use std::env;
use std::fs;
use toml;

// Logging imports.
use log::{error, info};
use anyhow::{Context, Result, anyhow};

// Application modules.
mod plugins;
mod config;
use config::config::{Config};
use config::errors::{Errors};
mod traps_utils;

// Constants.
const LOG4RS_CONFIG_FILE  : &str = "resources/log4rs.yml";
const ENV_CONFIG_FILE_KEY : &str = "TRAPS_CONFIG_FILE";
const DEFAULT_CONFIG_FILE : &str = "~/traps.toml";

fn main() -> Result<()> {
    // Write to stdout.
    println!("Starting camera-traps!");

    // Initialize log4rs logging.
    log4rs::init_file(LOG4RS_CONFIG_FILE, Default::default())
        .context(format!("{}", Errors::Log4rsInitialization(LOG4RS_CONFIG_FILE.to_string())))?;

    // Read input parameters.
    let parms = match get_parms() {
        Ok(p) => p,
        Err(e) => return Err(e),
    };
    
    info!("{}", Errors::InputParms(format!("{:#?}", parms)));

    // We're done.
    Ok(())
}

/** Retrieve the application parameters from the configuration file specified
 * either through an environment variable or as the first (and only) command
 * line argument.  If neither are provided, an attempt is made to use the
 * default file path.
 */
fn get_parms() -> Result<Parms> {
    // Get the config file path from the environment, command line or default.
    let config_file = env::var(ENV_CONFIG_FILE_KEY).unwrap_or_else(
        |_| {
            // Get the config file pathname as the first command line
            // parameter or use the default path.
            match env::args().nth(1) {
                Some(f) => f,
                None => DEFAULT_CONFIG_FILE.to_string()
            }
        });

    // Read the cofiguration file.
    let config_file_abs = traps_utils::get_absolute_path(&config_file);
    info!("{}", Errors::ReadingConfigFile(config_file_abs.clone()));
    let contents = match fs::read_to_string(&config_file_abs) {
        Ok(c) => c,
        Err(e) => {
            let msg = format!("{}\n   {}", Errors::FileIOError(config_file_abs), e);
            error!("{}", msg);
            return Result::Err(anyhow!(msg));
        }
    };

    // Parse the toml configuration.
    let config : Config = match toml::from_str(&contents) {
        Ok(c)  => c,
        Err(e) => {
            let msg = format!("{}\n   {}", Errors::TOMLParseError(config_file_abs), e);
            error!("{}", msg);
            return Result::Err(anyhow!(msg));
        }
    };

    Result::Ok(Parms { config_file: config_file_abs, config: config})
}

#[derive(Debug)]
struct Parms {
    config_file: String,
    config: Config,
}


#[cfg(test)]
mod tests {
    #[test]
    fn here_i_am() {
        println!("file test: main.rs");
    }
}
