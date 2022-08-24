// Stardard imports.
use std::env;
use std::fs;
use toml;

// Logging imports.
use log::{error, warn, info, debug, trace};
use anyhow::{Context, Result, anyhow};

// Application modules.
mod plugins;
mod config;
use config::config::{Config};
use config::errors::{Errors};

// Constants.
const LOG4RS_CONFIG_FILE  : &str = "resources/log4rs.yml";
const ENV_CONFIG_FILE_KEY : &str = "TRAPS_CONFIG_FILE";
const DEFAULT_CONFIG_FILE : &str = "resources/traps.toml";

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

/**
 * 
 */
fn get_parms() -> Result<Parms> {
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
    info!("{}", Errors::ReadingConfigFile(config_file.clone()));
    let contents = match fs::read_to_string(&config_file) {
        Ok(c) => c,
        Err(e) => {
            let msg = format!("{}\n   {}", Errors::FileIOError(config_file.clone()), e);
            error!("{}", msg);
            return Result::Err(anyhow!(msg));
        }
    };

    // Parse the toml configuration.
    let config : Config = match toml::from_str(&contents) {
        Ok(c)  => c,
        Err(e) => {
            let msg = format!("{}\n   {}", Errors::TOMLParseError(config_file), e);
            error!("{}", msg);
            return Result::Err(anyhow!(msg));
        }
    };

    Result::Ok(Parms { config_file: config_file, })
}

#[derive(Debug)]
struct Parms {
    config_file: String,
}


#[cfg(test)]
mod tests {
    #[test]
    fn here_i_am() {
        println!("file test: main.rs");
    }
}
