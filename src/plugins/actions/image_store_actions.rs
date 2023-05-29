//use std::cmp::PartialEq::max;
#[allow(unused_imports)]
use crate::{Config, traps_utils};
use crate::plugins::image_store_plugin::{ImageStorePlugin, StoreAction, StoreParms};
use crate::events_generated::gen_events::ImageScoredEvent;
use crate::{events, config::errors::Errors};
use event_engine::{plugins::Plugin};

use anyhow::{Result, anyhow};
use std::fs;
use serde_json;
use glob::glob;

use log::{info, error, warn, debug};

// The search string prefix for this plugin.
const PREFIX: &str  = "image_store_";

// The score file suffix.
const SCORE_SUFFIX: &str = "score";

// ***************************************************************************
//                            PUBLIC FUNCTIONS
// ***************************************************************************
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
pub fn select_action(config: &'static Config) -> Result<fn(&ImageStorePlugin, &ImageScoredEvent, &StoreParms)->StoreAction> {
    
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
            "image_store_noop_action" => {
                info!("{}", Errors::ActionConfigured("ImageStorePlugin".to_string(), action.to_string()));
                return Result::Ok(image_store_noop_action);
            },
            "image_store_file_action" => {
                info!("{}", Errors::ActionConfigured("ImageStorePlugin".to_string(), action.to_string()));
                return Result::Ok(image_store_file_action);
            },
            unknown => {
                let msg = Errors::ActionNotFound("ImageStorePlugin".to_string(), unknown.to_string());
                error!("{}", msg);
                return Result::Err(anyhow!(msg));
            }
        };
    }
    
    // Default is to take no action is specified for this plugin.
    Result::Ok(image_store_noop_action)
}

// ---------------------------------------------------------------------------
// image_store_noop_action:
// ---------------------------------------------------------------------------
/** No-op action. */
#[allow(unused)]
pub fn image_store_noop_action(plugin: &ImageStorePlugin, event: &ImageScoredEvent, 
                               store_parms_ref: &StoreParms) -> StoreAction {
    StoreAction::Noop
}

// ---------------------------------------------------------------------------
// image_store_file_action:
// ---------------------------------------------------------------------------
#[allow(unused)]
pub fn image_store_file_action(plugin: &ImageStorePlugin, event: &ImageScoredEvent, 
                               store_parms_ref: &StoreParms) -> StoreAction {

    // Find highest the score reported in the event.
    let highest_score = get_highest_score(event);

    // Get the action for the score.
    let store_action = get_action_for_score(store_parms_ref, highest_score);

    // Perform the action and return either the action taken or ErrorOut.
    match store_action {
        StoreAction::ErrorOut   => {StoreAction::ErrorOut}, // This is an output-only action and should never happen.
        StoreAction::Delete     => action_delete(plugin, event),
        StoreAction::Noop       => {StoreAction::Noop},
        StoreAction::ReduceSave => action_reduce_save(plugin, event),
        StoreAction::Save       => action_save(plugin, event),
    }
}

// ***************************************************************************
//                            PRIVATE FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// get_highest_score:
// ---------------------------------------------------------------------------
/** Return the highest score in the list of scores.  If no scores are present,
 * return 0.
 */
fn get_highest_score(event: &ImageScoredEvent) -> f32 {
    // Get a reference to the score vector.
    let scores = match event.scores() {
        Some(v) => v,
        None => return 0f32,
    };

    // Get the highest proabability of any score in the vector.
    let mut highest: f32 = 0f32; 
    for score in scores {
        highest = highest.max(score.probability());
    };

    highest
}

// ---------------------------------------------------------------------------
// get_action_for_score:
// ---------------------------------------------------------------------------
/** Compare the highest score for all against the configured thresholds.  The
 * highest threshold met determines the action.
 */
fn get_action_for_score(store_parms_ref: &StoreParms, score: f32) -> StoreAction {

    // Iterate through the threshold parameters configured at startup.
    // The alogorithm is find the first range that the highest event score
    // falls into.  The range thresholds are ordered from highest to lowest.
    // The action associated with the highest score's range is returned.
    for range in &store_parms_ref.config.action_thresholds {
        if score >= range.0 {
            return range.1.clone();
        }
    }
    
    // We should never get here since the store plugin guarantees
    // that a 0 range element is in the action_thresholds list.
    // The compiler doesn't know that, so this is necessary.
    StoreAction::Delete
}

// ---------------------------------------------------------------------------
// make_image_filepath:
// ---------------------------------------------------------------------------
/** Create absolute file path for the image.  The path conforms to this template:
 * 
 *   <image directory>/<filename prefix><image uuid>.<image format>
 * 
 * The image directory is always an absolute path.  The filename prefix can be 
 * the empty string.  Both of these values are part of the application configuration.
 * The image uuid and format are returned in the NewImageEvent. 
 */
#[allow(dead_code)]
fn make_image_filepath(plugin: &ImageStorePlugin, event: &ImageScoredEvent) -> Option<String> {
    // Get the uuid string for use in the file name.
    let uuid_str = match event.image_uuid() {
        Some(s) => s,
        None => {
            // Log the error and just return.
            let msg = format!("{}", Errors::PluginEventAccessUuidError(
                                      plugin.get_name(), "NewImageEvent".to_string()));
            error!("{}", msg);
            return None;
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
            return None;
        } 
    };

    // Get the path.
    let path = traps_utils::create_image_filepath(&plugin.get_runctx().abs_image_dir, 
                                                          &plugin.get_runctx().parms.config.image_file_prefix, 
                                                          uuid_str, 
                                                          suffix.as_str());

    Option::Some(path)
}

// ---------------------------------------------------------------------------
// make_score_filepath:
// ---------------------------------------------------------------------------
/** Create absolute file path for the image. The path conforms to this template:
 * 
 *   <image directory>/<filename prefix><image uuid>.score
 * 
 * The image directory is always an absolute path.  The filename prefix can be 
 * the empty string.  Both of these values are part of the application configuration.
 * The image uuid is returned in the NewImageEvent and the suffix is constant. 
 */
fn make_score_filepath(plugin: &ImageStorePlugin, event: &ImageScoredEvent) -> Option<String> {
    // Get the uuid string for use in the file name.
    let uuid_str = match event.image_uuid() {
        Some(s) => s,
        None => {
            // Log the error and just return.
            let msg = format!("{}", Errors::PluginEventAccessUuidError(
                                      plugin.get_name(), "NewImageEvent".to_string()));
            error!("{}", msg);
            return None;
        }
    };

    // Get the path.
    let path = traps_utils::create_image_filepath(&plugin.get_runctx().abs_image_dir, 
                                                          &plugin.get_runctx().parms.config.image_file_prefix, 
                                                          uuid_str, 
                                                          SCORE_SUFFIX);

    Option::Some(path)
}

// ---------------------------------------------------------------------------
// action_delete:
// ---------------------------------------------------------------------------
/** Delete all image related files and don't save the scores.  Image related
 * files are all file that match this format:
 * 
 *      <image_directory_path>/<image_file_prefix><image_uuid>*
 * 
 */
fn action_delete(plugin: &ImageStorePlugin, event: &ImageScoredEvent) -> StoreAction{
        // Get the uuid string for use in the file name.
    let uuid_str = match event.image_uuid() {
        Some(s) => s,
        None => {
            // Log the error and just return.
            let msg = format!("{}", Errors::PluginEventAccessUuidError(
                                      plugin.get_name(), "NewImageEvent".to_string()));
            error!("{}", msg);
            return StoreAction::ErrorOut
        }
    };

    // Get the path iterator that matches the wildcard path.
    let wildcard_path = 
        traps_utils::create_image_wildcard_path(&plugin.get_runctx().abs_image_dir, 
                                                &plugin.get_runctx().parms.config.image_file_prefix, 
                                                uuid_str);

    // Get path iterator and process its entries.
    match glob(&wildcard_path) {
        // Get an iterator to paths that match the filter.
        Err(e) => {
            // Log error.
            let msg = format!("{}", Errors::FileDeleteError(
                                      wildcard_path.clone(), e.to_string()));
            error!("{}", msg);
            return StoreAction::ErrorOut
        },
        Ok(path_iter) => {
            // Process each matching filepath.
            for entry in path_iter {
                match entry {
                    // Record the error and continue.
                    Err(e) => {
                        let msg = format!("{}", Errors::FileDeleteError(
                            wildcard_path.clone(), e.to_string()));
                        warn!("{}", msg);
                    },
                    Ok(path) => {
                        let filepath = path.as_os_str().to_str().unwrap();
                        match fs::remove_file(filepath){
                            Ok(_) => {
                                debug!("{}", format!("{}", Errors::FileDeleted(filepath.to_string())));
                            },
                            Err(e) => {
                                // Log error.
                                let msg = format!("{}", Errors::FileDeleteError(
                                                          filepath.to_string(), e.to_string()));
                                warn!("{}", msg);
                            }
                        }
                    }
                }
            }
        }
    }

    // Success though warnings may have been logged.
    StoreAction::Delete
}

// ---------------------------------------------------------------------------
// action_reduce_save:
// ---------------------------------------------------------------------------
/** Reduce the image resolution and then save it and it's scores.
 */
fn action_reduce_save(plugin: &ImageStorePlugin, event: &ImageScoredEvent) -> StoreAction {
    // TODO: reduce image size and replace existing image file.

    // Save the reduced image score.
    let result_action = action_save(plugin, event);
    if result_action == StoreAction::ErrorOut {
        return StoreAction::ErrorOut;
    }

    // Success.
    StoreAction::ReduceSave
}

// ---------------------------------------------------------------------------
// action_save:
// ---------------------------------------------------------------------------
/** Leave the image file as-is and save its scores.  On error, just log and return.
 */
fn action_save(plugin: &ImageStorePlugin, event: &ImageScoredEvent) -> StoreAction{
    // Extract the image uuid from the new image event.
    let image_scored_event = match events::ImageScoredEvent::new_from_gen(*event) {
        Ok(ev) => ev,
        Err(e) => {
            let msg = format!("{}", Errors::PluginEventDeserializationError(
                                      plugin.get_name(), "ImageScoredEvent".to_string()));           
            error!("{}: {}", msg, e.to_string());
            return StoreAction::ErrorOut;
        }
    };

    // Convert the event scores to json.
    let json_str = match serde_json::to_string(&image_scored_event) {
        Ok(s) => s,
        Err(e) => {
            let msg = format!("{}", Errors::EventToJsonError(
                                      plugin.get_name(), "ImageScoredEvent".to_string(), e.to_string()));           
            error!("{}", msg);
            return StoreAction::ErrorOut;
        }
    };

    // Construct the score output path name.
    let filepath = match make_score_filepath(plugin, event) {
        Some(fp)=> fp,
        None => {
            // Error already logged.
            return StoreAction::ErrorOut;
        }
    };

    // Write the json to the score output file.
    match traps_utils::create_or_replace_file(&filepath, json_str.as_bytes()) {
        Ok(_) => (),
        Err(e) => {
            let msg = format!("{}", Errors::ActionWriteFileError(plugin.get_name(),
                                      "action_save".to_string(), filepath, e.to_string()));
            error!("{}", msg);
            return StoreAction::ErrorOut;
        }
    };

    // Success.
    StoreAction::Save
}