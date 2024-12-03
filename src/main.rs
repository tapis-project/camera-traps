// Stardard imports.
use std::{env, fs, sync::Arc};
use lazy_static::lazy_static;

// Logging imports.
use log::{error, warn, info};
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
const ENV_LOG4RS_FILE_KEY : &str = "TRAPS_LOG4RS_CONFIG_FILE";
const LOG4RS_CONFIG_FILE  : &str = "resources/log4rs.yml";
const ENV_CONFIG_FILE_KEY : &str = "TRAPS_CONFIG_FILE";
const DEFAULT_CONFIG_FILE : &str = "~/traps.toml";

// ***************************************************************************
//                             Static Variables 
// ***************************************************************************
// Lazily initialize the parameters variable so that is has a 'static lifetime.
// We exit if we can't read our parameters.
lazy_static! {
    static ref RUNTIME_CTX: RuntimeCtx = init_runtime_context();
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
    log4rs::init_file(init_log_config(), Default::default())
        .context(format!("{}", Errors::Log4rsInitialization(init_log_config())))?;

    // Force the reading of input parameters and initialization of runtime context.
    info!("{}", Errors::InputParms(format!("{:#?}", *RUNTIME_CTX)));

    // File/dir creation and checking.
    traps_utils::validate_image_dir(&RUNTIME_CTX.parms.config, &RUNTIME_CTX.abs_image_dir)?;

    // Configure plugins.
    let app = init_app(&RUNTIME_CTX.parms)?;

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
fn init_app(parms: &'static Parms) -> Result<App, Errors>{
    
    // Create the app on the specified
    let mut app: App = App::new(parms.config.publish_port as i32, parms.config.subscribe_port as i32);

    // Internal plugins are optional.
    let int_plugins = match parms.config.plugins.internal.clone() {
        Some(v) => v,
        None => vec![]
    };

    // Help make the log more readable.
    let delimiter = "\n".to_string() + "-".repeat(70).as_str();
    info!("{}", delimiter.clone() + 
           (format!("{}",Errors::RegisteringNumInternalPlugins(int_plugins.len())) + delimiter.as_str()).as_str());

    // Register internal plugins if any are defined. 
    for plugin_name in &int_plugins {
        match plugin_name.as_str() {
            "image_gen_plugin" => {
                let plugin = ImageGenPlugin::new(&RUNTIME_CTX);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_gen_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "image_recv_plugin" => {
                let plugin = ImageReceivePlugin::new(&RUNTIME_CTX);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_recv_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "image_score_plugin" => {
                let plugin = ImageScorePlugin::new(&RUNTIME_CTX);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_score_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "image_store_plugin" => {
                let plugin = ImageStorePlugin::new(&RUNTIME_CTX);
                let uuid = plugin.get_id();
                info!("{}",Errors::RegisteringInternalPlugin("image_store_plugin".to_string(), uuid.hyphenated().to_string()));
                app = app.register_plugin(Arc::new(Box::new(plugin)));
            },
            "observer_plugin" => {
                let plugin = ObserverPlugin::new(&RUNTIME_CTX);
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

    // External plugins are optional.
    let ext_plugins = match parms.config.plugins.external.clone() {
        Some(v) => v,
        None => vec![]
    };

    // End internal plugin registration.
    info!("{}", delimiter.clone() + 
           (format!("{}",Errors::RegisteringNumExternalPlugins(ext_plugins.len())) + delimiter.as_str()).as_str());


    // Register external plugins if any are defined.
    for ext_plugin in &ext_plugins {
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
    if !ext_plugins.is_empty() {info!("{}", delimiter);}

    // Issue a warning if no plugins are configured.
    if int_plugins.is_empty() && ext_plugins.is_empty() {
        warn!("{}", Errors::PluginNone());
    }

    // Return the app.
    Result::Ok(app)
}

// ---------------------------------------------------------------------------
// init_runtime_context:
// ---------------------------------------------------------------------------
fn init_runtime_context() -> RuntimeCtx {
    // If either of these fail the application aborts.
    let parms = get_parms().expect("FAILED to read configuration file.");
    let abs_image_dir = init_image_dir(&parms.config.images_output_dir)
                                        .expect("FAILED to initialize image directory.");
    
    // Return the context.
    RuntimeCtx {parms, abs_image_dir}
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
fn init_image_dir(dir: &str) -> Result<String> {
    // Get the absolute filepath to the images directory.
    let abs_dir = traps_utils::get_absolute_path(dir);
    Result::Ok(abs_dir)
}

// ---------------------------------------------------------------------------
// init_log_config:
// ---------------------------------------------------------------------------
fn init_log_config() -> String {
    env::var(ENV_LOG4RS_FILE_KEY).unwrap_or_else(|_| LOG4RS_CONFIG_FILE.to_string())
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

// ---------------------------------------------------------------------------
// RuntimeCtx:
// ---------------------------------------------------------------------------
#[derive(Debug)]
pub struct RuntimeCtx {
    pub parms: Parms,
    pub abs_image_dir: String,
}

#[cfg(test)]
mod tests {
    #[test]
    fn here_i_am() {
        println!("file test: main.rs");
    }
}
