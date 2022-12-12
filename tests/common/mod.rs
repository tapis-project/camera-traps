// Stardard imports.
use std::{env, fs};
use std::ops::Deref;
use std::path::Path;

use anyhow::{Result, anyhow};
use path_absolutize::Absolutize;
use serde::Deserialize;

// ***************************************************************************
//                                Constants
// ***************************************************************************
// Constants.
const ENV_CONFIG_FILE_KEY : &str = "TRAPS_INTEGRATION_CONFIG_FILE";
const DEFAULT_CONFIG_FILE : &str = "~/traps-integration.toml";

// ***************************************************************************
//                                Functions
// ***************************************************************************
// ---------------------------------------------------------------------------
// get_parms:
// ---------------------------------------------------------------------------
/** Retrieve the application parameters from the configuration file specified
 * either through an environment variable or as the first (and only) command
 * line argument.  If neither are provided, an attempt is made to use the
 * default file path.
 */
pub fn get_parms() -> Result<Parms> {
    // Get the config file path from the environment, command line or default.
    let config_file = env::var(ENV_CONFIG_FILE_KEY).unwrap_or(DEFAULT_CONFIG_FILE.to_string());

    // Read the cofiguration file.
    let config_file_abs = get_absolute_path(&config_file);
    // println!("{}", Errors::ReadingConfigFile(config_file_abs.clone()));
    let contents = match fs::read_to_string(&config_file_abs) {
        Ok(c) => c,
        Err(e) => return Result::Err(anyhow!(e.to_string())),
    };

    // Parse the toml configuration.
    let config : Config = match toml::from_str(&contents) {
        Ok(c)  => c,
        Err(e) => return Result::Err(anyhow!(e.to_string())),
    };

    Result::Ok(Parms { config_file: config_file_abs, config})
}

// ***************************************************************************
// GENERAL PUBLIC FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// get_absolute_path:
// ---------------------------------------------------------------------------
/** Replace tilde (~) and environment variable values in a path name and
 * then construct the absolute path name.  The difference between 
 * absolutize and standard canonicalize methods is that absolutize does not 
 * care about whether the file exists and what the file really is.
 * 
 * Here's a short version of how canonicalize would be used: 
 * 
 *   let p = shellexpand::full(path).unwrap();
 *   fs::canonicalize(p.deref()).unwrap().into_os_string().into_string().unwrap()
 * 
 * We have the option of using these to two ways to generate a String from the
 * input path (&str):
 * 
 *   path.to_owned()
 *   path.deref().to_string()
 * 
 * I went with the former on a hunch that it's the most appropriate, happy
 * to change if my guess is wrong.
 */
fn get_absolute_path(path: &str) -> String {
    // Replace ~ and environment variable values if possible.
    // On error, return the string version of the original path.
    let s = match shellexpand::full(path) {
        Ok(x) => x,
        Err(_) => return path.to_owned(),
    };

    // Convert to absolute path if necessary.
    // Return original input on error.
    let p = Path::new(s.deref());
    let p1 = match p.absolutize() {
        Ok(x) => x,
        Err(_) => return path.to_owned(),
    };
    let p2 = match p1.to_str() {
        Some(x) => x,
        None => return path.to_owned(),
    };

    p2.to_owned()
}

// ***************************************************************************
//                                  Structs
// ***************************************************************************
// ---------------------------------------------------------------------------
// Parms:
// ---------------------------------------------------------------------------
#[derive(Debug)]
pub struct Parms {
    pub config_file: String,
    pub config: Config,
}

#[derive(Debug, Deserialize)]
pub struct Config {
    pub iterations: u32,
    pub image_input_dir: String,
    pub image_output_dir: String,
    pub external_plugin_config: ExtPluginConfig,
}

#[derive(Debug, Deserialize, Default)]
pub struct ExtPluginConfig {
    pub plugin_name: String,
    pub id: String,
    pub external_port: u16,
    pub subscriptions: Vec<String>,
}



