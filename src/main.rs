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
use event_engine::plugins::Plugin;
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

    // Register internal plugins. 
    for plugin_name in &parms.config.plugins.internal {
        match plugin_name.as_str() {
            "image_gen_plugin" => {
                let plugin = ImageGenPlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                app = app.register_plugin(Arc::new(Box::new(plugin)));
                info!("{}",Errors::PluginRegistered("image_gen_plugin".to_string(), uuid.hyphenated().to_string()));
            },
            "image_recv_plugin" => {
                let plugin = ImageReceivePlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                app = app.register_plugin(Arc::new(Box::new(plugin)));
                info!("{}",Errors::PluginRegistered("image_recv_plugin".to_string(), uuid.hyphenated().to_string()));
            },
            "image_score_plugin" => {
                let plugin = ImageScorePlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                app = app.register_plugin(Arc::new(Box::new(plugin)));
                info!("{}",Errors::PluginRegistered("image_score_plugin".to_string(), uuid.hyphenated().to_string()));
            },
            "image_store_plugin" => {
                let plugin =ImageStorePlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                app = app.register_plugin(Arc::new(Box::new(plugin)));
                info!("{}",Errors::PluginRegistered("image_store_plugin".to_string(), uuid.hyphenated().to_string()));
            },
            "observer_plugin" => {
                let plugin = ObserverPlugin::new(&PARMS.config);
                let uuid = plugin.get_id();
                app = app.register_plugin(Arc::new(Box::new(plugin)));
                info!("{}",Errors::PluginRegistered("observer_plugin".to_string(), uuid.hyphenated().to_string()));
            },
           other => {
                // Aborting.
                let err = Errors::PluginUnknown(other.to_string());
                error!("{}", err);
                return Result::Err(err);
            },
        }
    }

    // Register external plugins.
    for ext_plugin in &parms.config.plugins.external {
        let app_plugin = match ExternalAppPlugin::new(ext_plugin) {
            Ok(p) => p,
            Err(e) => return Result::Err(e),
        };

        // Register the external plugin.
        app = app.register_external_plugin(Arc::new(Box::new(app_plugin)));
    }

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
