use std::ops::Deref;
use std::path::Path;
use shellexpand;
use path_absolutize::Absolutize;
use chrono::{Utc, DateTime, FixedOffset, ParseError};
use uuid::Uuid;

use crate::events_generated::gen_events::{self, EventType};
use crate::config::errors::Errors;
use crate::events::{NewImageEvent, ImageReceivedEvent, ImageScoredEvent, ImageStoredEvent,
                    ImageDeletedEvent, PluginStartedEvent, PluginTerminateEvent, PluginTerminatingEvent};
use log::{error};

// ***************************************************************************
// CONSTANTS
// ***************************************************************************
// Used in termination processing.
const PLUGIN_NAME_WILDCARD: &str = "*";

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
pub fn get_absolute_path(path: &str) -> String {
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

// ---------------------------------------------------------------------------
// timestamp_str:
// ---------------------------------------------------------------------------
/** Get the current UTC timestamp as a string in rfc3339 format, which looks
 * like this:  2022-09-13T14:14:42.719849912+00:00
 */
pub fn timestamp_str() -> String {
    Utc::now().to_rfc3339()
}

// ---------------------------------------------------------------------------
// timestamp_str_to_datetime:
// ---------------------------------------------------------------------------
/** Convert a timestamp string in rfc3339 format (ex: 2022-09-13T14:14:42.719849912+00:00)
 * to a DateTime object.  The result will contain a parse error if the string
 * does not conform to rfc3339.
 */
pub fn timestamp_str_to_datetime(ts: &String) -> Result<DateTime<FixedOffset>, ParseError> {
    DateTime::parse_from_rfc3339(ts)
}

// ***************************************************************************
// EVENT PROCESSING
// ***************************************************************************
// ---------------------------------------------------------------------------
// bytes_to_gen_event:
// ---------------------------------------------------------------------------
pub fn bytes_to_gen_event(msg_bytes: &[u8]) -> Result<gen_events::Event, Errors> {
    // Read the byte array into a generated event backed by a flatbuffer.
    match gen_events::root_as_event(msg_bytes) {
        Ok(ev) => return Result::Ok(ev),
        Err(e) => {return Result::Err(Errors::EventFromFlatbuffer(e.to_string()));},
    };
}

// ---------------------------------------------------------------------------
// process_plugin_terminate_event:
// ---------------------------------------------------------------------------
/** Determine if the calling plugin is targeted for termination by the terminate 
 * event.  The input is the generated event, the plugin's uuid and the plugin's
 * name.    
 * 
 * Returns true if the plugin is targeted, false otherwise.  If the generated
 * event cannot be converted into an application event, then the error is logged
 * and false is returned.
 */
pub fn process_plugin_terminate_event(gen_event: gen_events::Event, uuid: &Uuid, plugin_name: &String) -> bool {
    let event = match gen_to_pluging_terminate_event(gen_event) {
        Ok(ev) => ev,
        Err(e) => {
            error!("{}", e.to_string());
            return false
        },
    };

    // See if the calling plugin is the target either
    // explicitly by name or by wildcard.
    if event.target_plugin_name.eq(plugin_name) || 
       event.target_plugin_name.eq(PLUGIN_NAME_WILDCARD) {
        return true;
    }

    // See if the calling plugin's uuid is the target.
    if event.target_plugin_uuid.eq(uuid) {
        return true;
    }

    // We're not the target of the terminate event.
    false
}

// ***************************************************************************
// GENERATED EVENT TO CAMERA EVENT FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// gen_to_new_image_event:
// ---------------------------------------------------------------------------
pub fn gen_to_new_image_event(gen_event: gen_events::Event) -> Result<NewImageEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_new_image_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("NewImageEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match NewImageEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => return Result::Ok(ev),
        Err(e) => return Result::Err(e),
    };
}

// ---------------------------------------------------------------------------
// gen_to_pluging_terminate_event:
// ---------------------------------------------------------------------------
pub fn gen_to_pluging_terminate_event(gen_event: gen_events::Event) -> Result<PluginTerminateEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_plugin_terminate_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("PluginTerminateEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match PluginTerminateEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => return Result::Ok(ev),
        Err(e) => return Result::Err(e),
    };
}



mod tests {
    use crate::traps_utils::*;

    #[test]
    fn here_i_am() {
        println!("file test: traps_utils.rs");

        // Test timestamp string inversion: string to datetime back to string
        let s1 = timestamp_str();
        println!("current utc timestamp: {}", s1);
        let ts1 = timestamp_str_to_datetime(&s1).unwrap();
        let s2 = ts1.to_rfc3339();
        assert_eq!(s1, s2);
    }
}
