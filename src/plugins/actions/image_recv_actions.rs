use std::fs::OpenOptions;
use std::io::Write;

use crate::{Config, traps_utils};
use crate::plugins::image_recv_plugin::ImageReceivePlugin;
use event_engine::{plugins::Plugin};
use crate::{config::errors::Errors};
use crate::events_generated::gen_events::NewImageEvent;
use anyhow::{Result, anyhow};

use log::{info, error};

// The search string prefix for this plugin.
const PREFIX: &str  = "image_recv_";

// ---------------------------------------------------------------------------
// select_action:
// ---------------------------------------------------------------------------
/** Called one time by each internal plugin to select their single action function. 
 * The internal_actions array component of the plugins configuration object lists
 * zero or more function names.  Each function name is associated with one of the 
 * defined plugins using a convention.  The convention is that each function begins
 * with a prefix derived from the plugin name by dropping the "plugin.rs" portion
 * of the plugin file's name.
 * 
 * This function returns the first function named in internal_actions that matches
 * the plugin's prefix string.  If no such entry is found, the no-op action is 
 * returned.  If a matching entry does not correspond to an action function defined
 * in this file, then an error is returned.
 * 
 * Each action function associated with this plugin requires an arm in the match 
 * statement, which requires maintenance when new action functions are developed. 
 */
pub fn select_action(config: &'static Config) -> Result<fn(&ImageReceivePlugin, &NewImageEvent) -> bool > {
    
    // Internal plugins are optional.
    let int_actions = match config.plugins.internal_actions.clone() {
        Some(v) => v,
        None => vec![]
    };

    // Iterate through all configured actions looking for the one
    // that targets this plugin.  The convention is that a plugin's
    // actions start with a prefix of plugin's file name (i.e., the
    // text preceeding 'plugin.rs').
    for action in &int_actions {
        // See if the current action is for this plugin.
        if !(*action).starts_with(PREFIX) {continue;}

        // We expect an implemented function to match the name.
        match action.as_str() {
            "image_recv_noop_action" => {
                info!("{}", Errors::ActionConfigured("ImageReceivePlugin".to_string(), action.to_string()));
                return Result::Ok(image_recv_noop_action);
            },
            "image_recv_write_file_action" => {
                info!("{}", Errors::ActionConfigured("ImageReceivePlugin".to_string(), action.to_string()));
                return Result::Ok(image_recv_write_file_action);
            },
            unknown => {
                let msg = Errors::ActionNotFound("ImageReceivePlugin".to_string(), unknown.to_string());
                error!("{}", msg);
                return Result::Err(anyhow!(msg));
            }
        };
    }
    
    // Default is to take no action is specified for this plugin.
    Result::Ok(image_recv_noop_action)
}

// ---------------------------------------------------------------------------
// image_recv_noop_action:
// ---------------------------------------------------------------------------
/** No-op action always returns true to allow processing to continue. */
#[allow(unused)]
pub fn image_recv_noop_action(plugin: &ImageReceivePlugin, event: &NewImageEvent) -> bool 
{true}

// ---------------------------------------------------------------------------
// image_recv_write_file_action:
// ---------------------------------------------------------------------------
/** Write image to file.  Return true if task complete successfully, otherwise
 * return false to abort processing for this image.
*/
pub fn image_recv_write_file_action(plugin: &ImageReceivePlugin, event: &NewImageEvent) -> bool {

    // There's no point in moving on if we can't access the image data.
    let bytes = match event.image() {
        Some(b) => b,
        None => {
            let msg = format!("{}", Errors::ActionNoImageError(
                                      plugin.get_name(), "image_recv_write_file_action".to_string(),
                                      "NewImageEvent".to_string(),
                                    ));
            error!("{}", msg);
            return false;
        } 
    };
    
    // Get the uuid string for use in the file name.
    let uuid_str = match event.image_uuid() {
        Some(s) => s,
        None => {
            // Log the error and just return.
            let msg = format!("{}", Errors::PluginEventAccessUuidError(
                                      plugin.get_name(), "NewImageEvent".to_string()));
            error!("{}", msg);
            return false;
        }
    };

    // Standardize image type suffixes to lowercase.
    let suffix = match event.image_format() {
        Some(s) => s.to_string().to_lowercase(),
        None => {
            // Log the error and just return.
            let msg = format!("{}", Errors::ActionImageFormatTypeError(
                                      plugin.get_name(), "NewImageEvent".to_string()));
            error!("{}", msg);
            return false;
        } 
    };

    // Create absolute file path for the image.
    let filepath = create_image_filepath(plugin, uuid_str, &suffix);

    // Open the image output file.
    let mut file = match OpenOptions::new()
                        .write(true)
                        .create(true)
                        .truncate(true)
                        .open(&filepath) {
                            Ok(f) => f,
                            Err(e) => {
                                let msg = format!("{}", Errors::ActionOpenFileError(
                                    plugin.get_name(), "image_recv_write_file_action".to_string(), 
                                    filepath, e.to_string()));
                                error!("{}", msg);
                                return false;
                            }
    };

    // Write the image bytes to file.  We always return ().
    match file.write_all(bytes) {
        Ok(_) => (),
        Err(e) => {
            let msg = format!("{}", Errors::ActionWriteFileError(
                plugin.get_name(), "image_recv_write_file_action".to_string(), 
                filepath, e.to_string()));
            error!("{}", msg);
            return false;
        }
    }

    // Success
    true
}

// ---------------------------------------------------------------------------
// create_image_filepath:
// ---------------------------------------------------------------------------
/** Create absolute file path for the image. */
fn create_image_filepath(plugin: &ImageReceivePlugin, uuid_str: &str, suffix: &str) -> String {
    return traps_utils::create_image_filepath(&plugin.get_runctx().abs_image_dir, 
                                              &plugin.get_runctx().parms.config.image_file_prefix, 
                                              uuid_str, 
                                              suffix);
}
