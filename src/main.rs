// Stardard imports.
use std::{env, fs};
use toml;

// Logging imports.
use log::{error, info};
use anyhow::{Context, Result, anyhow};

// Application modules.
mod plugins;
mod config;
mod events;
mod events_generated;
pub mod traps_utils;
use config::config::{Config};
use config::errors::{Errors};

// Event engine imports.
use event_engine::App;

// ***************************************************************************
//                                Constants
// ***************************************************************************
// Constants.
const LOG4RS_CONFIG_FILE  : &str = "resources/log4rs.yml";
const ENV_CONFIG_FILE_KEY : &str = "TRAPS_CONFIG_FILE";
const DEFAULT_CONFIG_FILE : &str = "~/traps.toml";

// ***************************************************************************
//                                Functions
// ***************************************************************************
// ---------------------------------------------------------------------------
// main:
// ---------------------------------------------------------------------------
fn main() -> Result<()> {
    // Write to stdout.
    println!("Starting camera-traps!");

    // Initialize log4rs logging.
    log4rs::init_file(LOG4RS_CONFIG_FILE, Default::default())
        .context(format!("{}", Errors::Log4rsInitialization(LOG4RS_CONFIG_FILE.to_string())))?;

    // Read input parameters.
    let parms = get_parms()?;
    info!("{}", Errors::InputParms(format!("{:#?}", parms)));

    // Start internal plugins.
    let app = init_app(parms)?;


    // We're done.
    Ok(())
}

// ---------------------------------------------------------------------------
// initApp:
// ---------------------------------------------------------------------------
fn init_app(parms: Parms) -> Result<App>{
    
    // Create the app on the specified
    let app: App = App::new(parms.config.publish_port as i32, parms.config.subscribe_port as i32);
    
    // Register internal plugins.


    // Register external plugins.


    // Return the app.
    Result::Ok(app)
}

// ---------------------------------------------------------------------------
// get_parms:
// ---------------------------------------------------------------------------
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

// ***************************************************************************
//                                  Structs
// ***************************************************************************
// ---------------------------------------------------------------------------
// Parms:
// ---------------------------------------------------------------------------
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
