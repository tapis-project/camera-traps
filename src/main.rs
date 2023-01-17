// Stardard imports.
use std::{env, fs, sync::Arc};
use lazy_static::lazy_static;

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
use event_engine::plugins::{Plugin, ExternalPlugin};
use plugins::{image_gen_plugin::ImageGenPlugin, image_recv_plugin::ImageReceivePlugin,
              image_score_plugin::ImageScorePlugin, image_store_plugin::ImageStorePlugin,
              observer_plugin::ObserverPlugin, external_app_plugin::ExternalAppPlugin};

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
//                             Static Variables 
// ***************************************************************************
// Lazily initialize the parameters variable so that is has a 'static lifetime.
// We exit if we can't read our parameters.
lazy_static! {
    static ref PARMS: Parms = get_parms().unwrap();
    pub static ref ABS_IMAGE_PATH: String = init_image_dir().unwrap();
}

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

    // Force the reading of input parameters.
    info!("{}", Errors::InputParms(format!("{:#?}", *PARMS)));

    // File/dir creation and checking.
    //traps_utils::validate_image_dir(&ABS_IMAGE_PATH)?;
    traps_utils::validate_image_dir(&PARMS.config, &ABS_IMAGE_PATH)?;

    // Configure plugins.
    let app = init_app(&PARMS)?;

    // Run the event engine.
    match app.run() {
        Ok(_) => (),
        Err(e) => {
            let msg = Errors::AppErrorShutdown(e.to_string());
            error!("{}", msg);
            return Result::Err(anyhow!(msg));
        },
    };

    // We're done.
    info!("{}", Errors::AppNormalShutdown());
    Ok(())
}

// ---------------------------------------------------------------------------
// initApp:
// ---------------------------------------------------------------------------
fn init_app(parms: &Parms) -> Result<App, Errors>{
    
    // Create the app on the specified
    let mut app: App = App::new(parms.config.publish_port as i32, parms.config.subscribe_port as i32);

    // Help make the log more readable.
    let delimiter = "\n".to_string() + "-".repeat(70).as_str();
    info!("{}", delimiter.clone() + 
           (format!("{}",Errors::RegisteringNumInternalPlugins(parms.config.plugins.internal.len())).to_string() + delimiter.as_str()).as_str());

    // Register internal plugins if any are defined. 
    for plugin_name in &parms.config.plugins.internal {
        match plugin_name.as_str() {
            "image_gen_plugin" => {
                let plugin = ImageGenPlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_gen_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "image_recv_plugin" => {
                let plugin = ImageReceivePlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_recv_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "image_score_plugin" => {
                let plugin = ImageScorePlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_score_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "image_store_plugin" => {
                let plugin =ImageStorePlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_store_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "observer_plugin" => {
                let plugin = ObserverPlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                info!("{}", Errors::RegisteringInternalPlugin("observer_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
           other => {
                // Aborting.
                let err = Errors::PluginUnknown(other.to_string());
                error!("{}", err);
                return Result::Err(err);
            },
        }
    }

    // End internal plugin registration.
    info!("{}", delimiter.clone() + 
           (format!("{}",Errors::RegisteringNumExternalPlugins(parms.config.plugins.external.len())).to_string() + delimiter.as_str()).as_str());


    // Register external plugins if any are defined.
    for ext_plugin in &parms.config.plugins.external {
        let app_plugin = match ExternalAppPlugin::new(ext_plugin) {
            Ok(p) => p,
            Err(e) => return Result::Err(e),
        };

        // Register the external plugin
        let cnt = app_plugin.get_subscriptions().unwrap().len();
        let id = app_plugin.get_id().hyphenated().to_string();
        info!("{}", Errors::RegisteringExternalPlugin(app_plugin.get_name(), id, app_plugin.get_tcp_port(), cnt));
        app = app.register_external_plugin(Arc::new(Box::new(app_plugin)));
    }

    // End plugin registration.
    if parms.config.plugins.external.len() > 0 {info!("{}", delimiter);}

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

    Result::Ok(Parms { config_file: config_file_abs, config})
}

// ---------------------------------------------------------------------------
// init_image_dir:
// ---------------------------------------------------------------------------
fn init_image_dir() -> Result<String> {
    // Get the absolute filepath to the images directory.
    let abs_dir = traps_utils::get_absolute_path(PARMS.config.images_dir.as_str());
    return Result::Ok(abs_dir);
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
