use std::ops::Deref;
use std::path::Path;
use std::fs;
use std::os::unix::fs::MetadataExt;
use std::io::Write;

use event_engine::events::{Event, EventType,};
use event_engine::plugins::Plugin;
use event_engine::errors::EngineError;
use path_absolutize::Absolutize;
use chrono::{Utc, DateTime, FixedOffset, ParseError};
use uuid::Uuid;
use zmq::Socket;

use crate::events_generated::gen_events;
use crate::events;
use crate::config::{errors::Errors, config::Config};
use crate::events::{NewImageEvent, ImageReceivedEvent, ImageScoredEvent, ImageStoredEvent,
                    ImageDeletedEvent, PluginStartedEvent, PluginTerminateEvent, PluginTerminatingEvent,
                    MonitorPowerStartEvent, MonitorPowerStopEvent};
use log::{error};

// ***************************************************************************
// CONSTANTS
// ***************************************************************************
// Used in termination processing.
const PLUGIN_NAME_WILDCARD: &str = "*";

// An rfc3339 compliant datetime from the past.
#[allow(dead_code)]
pub const PAST_DATETIME: &str = "2000-01-01T00:00:00+00:00";

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
#[allow(dead_code)]
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
// create_image_filepath:
// ---------------------------------------------------------------------------
/** Create absolute file path for the image. */
#[allow(dead_code)]
pub fn create_image_filepath(abs_dir: &str, image_file_prefix: &Option<String>, 
                             uuid_str: &str, suffix: &str) -> String {
    // Get absolute path of the image directory with a trailing slash.
    let slash = if abs_dir.ends_with('/') {""} else {"/"};
    let mut filepath = abs_dir.to_owned();
    filepath.push_str(slash);

    // Prepend the file prefix if one is specified.
    match image_file_prefix {
        Some(s) => filepath.push_str(s),
        None => {}
    }

    // Append the image uuid as the file name and 
    // the image type as the file extension.
    filepath.push_str(uuid_str);
    filepath.push('.');
    filepath.push_str(suffix);
    filepath
}

// ---------------------------------------------------------------------------
// create_image_wildcard_path:
// ---------------------------------------------------------------------------
/** Create a file path using the glob wildcard characters that would that 
 * capture all files related to an image.  The result is string that can be 
 * used to search for all files in a directory that are related to or stem from
 * an image file, including the image file itself.  The format of the result
 * string is:
 * 
 *    <image_directory_path>/<image_file_prefix><image_uuid>*
 *  
 * Using above constructed strings with the glob search crate allows all 
 * imaged related files to be discovered.
 *
 */
#[allow(dead_code)]
pub fn create_image_wildcard_path(abs_dir: &str, image_file_prefix: &Option<String>, 
                             uuid_str: &str) -> String {
    // Get absolute path of the image directory with a trailing slash.
    let slash = if abs_dir.ends_with('/') {""} else {"/"};
    let mut filepath = abs_dir.to_owned();
    filepath.push_str(slash);

    // Prepend the file prefix if one is specified.
    match image_file_prefix {
        Some(s) => filepath.push_str(s),
        None => {}
    }

    // Append the image uuid as the file name and the wildcare.
    filepath.push_str(uuid_str);
    filepath.push('*');
    filepath
}

// ---------------------------------------------------------------------------
// validate_image_dir:
// ---------------------------------------------------------------------------
/** Check if we have r/w/x permission on the local image directory if that
 * directory is used by one of the plugins.  This method will create the directory 
 * if necessary.  
 * 
 * This method is expected to be called once at application start up so that 
 * the execution can be aborted if no image I/O will be possible.
 */
#[allow(dead_code)]
pub fn validate_image_dir(config: &Config, abs_dir: &String) -> Result<(), Errors> {

    // Internal plugins are optional.
    let int_actions = match config.plugins.internal_actions.clone() {
        Some(v) => v,
        None => return Ok(()), 
    };
    
    // Determine if we are using local storage for image files.
    if !uses_local_image_dir(&int_actions) {return Ok(());}

    // Create the directory if it doesn't exist.  If the path
    // leads to an existing file, this call will fail (not tested
    // with symbolic links).
    match fs::create_dir_all(abs_dir) {
        Ok(_) => (),
        Err(e) => {
            let err = Errors::AppDirCreateError(abs_dir.clone(), e.to_string());
            error!("{}", err);
            return Result::Err(err);
        }
    };
    
    // Check permissions on the directory.
    let meta = match fs::metadata(abs_dir.as_str()) {
        Ok(m) => m,
        Err(e) => {
            let err = Errors::AppDirPermissionError(abs_dir.clone(), "read/write".to_string(), e.to_string());
            error!("{}", err);
            return Result::Err(err);
        }
    };

    // Get the mode bits and check that we have r/w/x access to the directory.
    let mode = meta.mode();
    let user_rw_access  = mode & 0o700;
    let group_rw_access = mode & 0o070;
    let other_rw_access = mode & 0o007;
    if user_rw_access != 0o700 && group_rw_access != 0o070 && other_rw_access != 0o007 {
        let err = Errors::AppDirPermissionError(abs_dir.clone(), "read/write".to_string(), 
                                                        "Permission check failed".to_string());
        error!("{}", err);
        return Result::Err(err);
    }

    // The directory exists and is r/w.
    Ok(())
}    

// ---------------------------------------------------------------------------
// uses_local_image_dir:
// ---------------------------------------------------------------------------
/** Check if any of the configured plugin actions requires a local image
 * directory for I/O.  We hardcode the plugin actions that use the image
 * directory, which requires maintenance when new actions are introduced. 
 */
fn uses_local_image_dir(configured_actions: &Vec<String>) -> bool {
    
    // Hardcode the actions that require a local image directory. Since
    // this method only gets called once per application execution, we
    // put the list on the stack so it gets cleaned up.  This vector 
    // may need to be updated when new actions are developed.
    let local_store_actions = vec!["image_recv_write_file_action", "image_store_file_action"];
    
    // Determine if any of the configured actions match the 
    // hardcoded actions that requre a local image directory.
    for action in configured_actions {
        if local_store_actions.contains(&action.as_str()) {return true;}
    }
    
    // Local image directory is not needed.
    false
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
#[allow(dead_code)]
pub fn timestamp_str_to_datetime(ts: &str) -> Result<DateTime<FixedOffset>, ParseError> {
    DateTime::parse_from_rfc3339(ts)
}

// ---------------------------------------------------------------------------
// create_or_replace_file:
// ---------------------------------------------------------------------------
/** Create a file if it doesn't exist, then write the data to it replacing any
 * existing content.
 */
#[allow(dead_code)]
pub fn create_or_replace_file(filepath: &String, buf: &[u8]) -> Result<(), std::io::Error> {
    let mut file = fs::File::create(filepath)?;
    file.write_all(buf)
}

// ***************************************************************************
// EVENT PROCESSING
// ***************************************************************************
// ---------------------------------------------------------------------------
// bytes_to_gen_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn bytes_to_gen_event(msg_bytes: &[u8]) -> Result<gen_events::Event, Errors> {
    // Read the byte array into a generated event backed by a flatbuffer.
    match gen_events::root_as_event(msg_bytes) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => {Result::Err(Errors::EventFromFlatbuffer(e.to_string()))},
    }
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
#[allow(dead_code)]
pub fn process_plugin_terminate_event(gen_event: gen_events::Event, uuid: &Uuid, plugin_name: &String) -> bool {
    let event = match gen_to_plugin_terminate_event(gen_event) {
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

// ---------------------------------------------------------------------------
// send_terminating_event:
// ---------------------------------------------------------------------------
/** This method quietly sends the calling plugin's terminating event.
 * Errors are logged but not surfaced.
 */
#[allow(dead_code)]
pub fn send_terminating_event(plugin_name: &String, plugin_uuid: Uuid, pub_socket: &Socket) {
    // Create the event for the calling plugin.
    let ev = PluginTerminatingEvent::new(plugin_uuid, plugin_name.to_string());

    // Serialize the event.
    let data = match ev.to_bytes() {
        Ok(d) => d,
        Err(e) => {
            // Log the error.
            let err = Errors::EventToBytesError(plugin_name.to_string(), ev.get_name(), e.to_string());
            error!("{}", format!("{}", err));
            return;
        }
    };

    // Send the event.
    match pub_socket.send(&data, 0) {
        Ok(_) => (),
        Err(e) => {
            // Log the error.
            let err = Errors::EventSendError(plugin_name.to_string(), ev.get_name(), e.to_string());
            error!("{}", format!("{}", err));
        },
    };
}

// ---------------------------------------------------------------------------
// send_started_event:
// ---------------------------------------------------------------------------
/** Plugins call this method to send their initial event announcing their execution.
 * If the transmission fails for any reason the calling plugin will receive an error
 * and should abort.
 */
#[allow(dead_code)]
pub fn send_started_event(plugin: &dyn Plugin, pub_socket: &Socket) -> Result<(), EngineError> {
    // Send our alive event.
    let ev = PluginStartedEvent::new(plugin.get_id(), plugin.get_name());
        let bytes = match ev.to_bytes() {
        Ok(v) => v,
        Err(e) => {
            // Log the error and abort if we can't serialize our start up message.
            let msg = format!("{}", Errors::EventToBytesError(plugin.get_name(), ev.get_name(), e.to_string()));
            error!("{}", msg);
            return Err(EngineError::PluginExecutionError(plugin.get_name(), plugin.get_id().hyphenated().to_string(), msg));
        } 
    };

    // Send the event serialization succeeded.
    match pub_socket.send(bytes, 0) {
        Ok(_) => (),
        Err(e) => {
            // Log the error and abort if we can't send our start up message.
            let msg = format!("{}", Errors::SocketSendError(plugin.get_name(), ev.get_name(), e.to_string()));
            error!("{}", msg);
            return Err(EngineError::PluginExecutionError(plugin.get_name(), plugin.get_id().hyphenated().to_string(), msg));
        }
    };
    
    // All good.
    Result::Ok(())
}

// ***************************************************************************
// INCOMING EVENT COMMON PROCESSING
// ***************************************************************************
/// Container for incoming events that have been marshalled into prefix
/// and flatbuffer event. 
#[allow(dead_code)]
pub struct IncomingEvent<'a> {
    pub prefix_array: [u8; 2],
    pub gen_event: gen_events::Event<'a>,
}

// ---------------------------------------------------------------------------
// marshal_next_event:
// ---------------------------------------------------------------------------
/** This method is called by plugins in their main event reading loop.  This
 * method performs the following:
 * 
 *  - Wait for the next event to arrive
 *  - Copy the raw bytes into the caller's buffer
 *  - Validate the minimum input length
 *  - Parse the flatbuffer into a generated event type
 *  - Validate that the prefix bytes and the event name agree
 *  - Return the prefix bytes and generated event
 * 
 * Any failure skips the rest of the processing and returns None. 
 */
#[allow(dead_code)]
pub fn marshal_next_event<'a>(plugin: &dyn Plugin, sub_socket: &Socket, bytes: &'a mut Vec<u8>)
    -> Option<IncomingEvent<'a>> {
    // ----------------- Retrieve and Slice Raw Bytes -----------------
    // Wait on the subsciption socket.
    let temp = match sub_socket.recv_bytes(0) {
        Ok(b) => b,
        Err(e) => {
            // We log error and then move on. It would probably be a good idea to 
            // pause before continuing if there are too many errors in a short period
            // of time.  This would avoid filling up the log file and burning cycles
            // when things go sideways for a while.
            error!("{}", Errors::SocketRecvError(plugin.get_name(), e.to_string()));
            return Option::None;
        }
    };
    // We copy the incoming bytes to the caller's vector and then use that vector 
    // for all further processing. Specifically, the references returned by this
    // function are backed by the caller's vector which has the required lifetime. 
    bytes.extend_from_slice(&temp);

    // Basic buffer length checking to make sure we have
    // the event prefix and at least 1 other byte.
    if bytes.len() < events::EVENT_PREFIX_LEN + 1 {
        error!("{}", Errors::EventInvalidLen(plugin.get_name(), bytes.len()));
        return Option::None;
    }

    // Split the 2 zqm prefix bytes from the flatbuffer bytes.
    let prefix_bytes = &bytes[0..events::EVENT_PREFIX_LEN];
    let fbuf_bytes = &bytes[events::EVENT_PREFIX_LEN..];

    // ----------------- Get the FBS Generated Event ------------------
    // Get the generated event and its type.
    let gen_event = match bytes_to_gen_event(fbuf_bytes) {
        Ok(tuple)=> tuple,
        Err(e)=> {
            error!("{}", e.to_string());
            return Option::None;
        }
    };

    // Get the event name from the generated event and check it against prefix slice.
    let event_name = match gen_event.event_type().variant_name() {  
        Some(n) => n,
        None => {
            error!("{}", Errors::EventNoneError(plugin.get_name()));
            return Option::None;
        },
    };

    // ----------------- Check the Prefix and Event -------------------
    // Check that the prefix bytes match the event type. 
    // False means a mismatch was detected and the 
    let prefix_array = [prefix_bytes[0], prefix_bytes[1]];
    if !events::check_event_prefix(prefix_array, event_name) {
        let pre = format!("{:?}", prefix_array);
        let name = event_name.to_string();
        error!("{}", Errors::EventPrefixMismatch(plugin.get_name(), pre, name));
        return Option::None;
    }

    // Pass back the event components.
    Option::Some(IncomingEvent { prefix_array, gen_event })
}

// ***************************************************************************
// GENERATED-EVENT TO CAMERA-EVENT FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// gen_to_new_image_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_new_image_event(gen_event: gen_events::Event) -> Result<NewImageEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_new_image_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("NewImageEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match NewImageEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_image_received_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_image_received_event(gen_event: gen_events::Event) -> Result<ImageReceivedEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_image_received_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("ImageReceivedEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match ImageReceivedEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_image_stored_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_image_scored_event(gen_event: gen_events::Event) -> Result<ImageScoredEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_image_scored_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("ImageScoredEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match ImageScoredEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_image_deleted_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_image_stored_event(gen_event: gen_events::Event) -> Result<ImageDeletedEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_image_deleted_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("ImageDeletedEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match ImageDeletedEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_image_deleted_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_image_deleted_event(gen_event: gen_events::Event) -> Result<ImageStoredEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_image_stored_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("ImageStoredEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match ImageStoredEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_pluging_started_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_plugin_started_event(gen_event: gen_events::Event) -> Result<PluginStartedEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_plugin_started_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("PluginStartedEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match PluginStartedEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_plugin_terminate_event:
// ---------------------------------------------------------------------------
pub fn gen_to_plugin_terminate_event(gen_event: gen_events::Event) -> Result<PluginTerminateEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_plugin_terminate_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("PluginTerminateEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match PluginTerminateEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_plugin_terminating_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_plugin_terminating_event(gen_event: gen_events::Event) -> Result<PluginTerminatingEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_plugin_terminating_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("PluginTerminatingEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match PluginTerminatingEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_monitor_power_start_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_monitor_power_start_event(gen_event: gen_events::Event) -> Result<MonitorPowerStartEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_monitor_power_start_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("MonitorPowerStartEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match MonitorPowerStartEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}

// ---------------------------------------------------------------------------
// gen_to_monitor_power_stop_event:
// ---------------------------------------------------------------------------
#[allow(dead_code)]
pub fn gen_to_monitor_power_stop_event(gen_event: gen_events::Event) -> Result<MonitorPowerStopEvent, Errors> {
    // Create the generated event from the raw flatbuffer.
    let flatbuf_event = match gen_event.event_as_monitor_power_stop_event() {
        Some(ev) => ev,
        None =>  return Result::Err(Errors::EventCreateFromFlatbuffer("MonitorPowerStoptEvent".to_string())), 
    };

    // Return a camera-trap event given the flatbuffer generated event.
    match MonitorPowerStopEvent::new_from_gen(flatbuf_event) {
        Ok(ev) => Result::Ok(ev),
        Err(e) => Result::Err(e),
    }
}


mod tests {
    #[allow(unused_imports)]
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
