//use std::cmp::PartialEq::max;
#[allow(unused_imports)]
use crate::{Config, traps_utils};
use crate::plugins::image_store_plugin::{ImageStorePlugin, StoreAction, StoreParms};
use crate::events_generated::gen_events::ImageScoredEvent;
use crate::{config::errors::Errors};
use anyhow::{Result, anyhow};


use log::{info, error};

// The search string prefix for this plugin.
const PREFIX: &str  = "image_store_";

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

    // Perform the action.
    match store_action {
        StoreAction::Delete => action_delete(event),
        StoreAction::Noop   => action_noop(event),
        StoreAction::ReduceSave => action_reduce_save(event),
        StoreAction::Save       => action_save(event),
    }

    // Return the action taken.
    store_action
}

// ***************************************************************************
//                            PRIVATE FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// get_highest_score:
// ---------------------------------------------------------------------------
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
// create_image_filepath:
// ---------------------------------------------------------------------------
/** Create absolute file path for the image. */
fn create_image_filepath(plugin: &ImageStorePlugin, uuid_str: &str, suffix: &str) -> String {
    return traps_utils::create_image_filepath(&plugin.get_runctx().abs_image_dir, 
                                              &plugin.get_runctx().parms.config.image_file_prefix, 
                                              uuid_str, 
                                              suffix);
}

// ---------------------------------------------------------------------------
// action_delete:
// ---------------------------------------------------------------------------
fn action_delete(event: &ImageScoredEvent) {
    let uuid = event.image_uuid();
}

// ---------------------------------------------------------------------------
// action_noop:
// ---------------------------------------------------------------------------
fn action_noop(event: &ImageScoredEvent) {

}

// ---------------------------------------------------------------------------
// action_reduce_save:
// ---------------------------------------------------------------------------
fn action_reduce_save(event: &ImageScoredEvent) {

}
// ---------------------------------------------------------------------------
// action_save:
// ---------------------------------------------------------------------------
fn action_save(event: &ImageScoredEvent) {

}