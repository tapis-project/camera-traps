use std::collections::BTreeMap;
use uuid::Uuid;
use zmq::Socket;
use serde::Deserialize;
use std::{env, fs};
use anyhow::{Result, anyhow};
use event_engine::{plugins::Plugin};
use event_engine::errors::EngineError;
use event_engine::events::EventType;
use event_engine::events::Event;
use crate::events_generated::gen_events;
use crate::{events, config::errors::Errors};
use crate::{traps_utils, RuntimeCtx};
#[allow(unused_imports)]
use crate::Config;
use crate::events::{IMAGE_SCORED_PREFIX, PLUGIN_TERMINATE_PREFIX};
use crate::plugins::actions::image_store_actions::select_action;

use log::{info, error, debug};

// ***************************************************************************
//                                Constants
// ***************************************************************************
// Constants.
#[allow(dead_code)]
const ENV_CONFIG_FILE_KEY : &str = "TRAPS_IMAGE_STORE_FILE";
#[allow(dead_code)]
const DEFAULT_CONFIG_FILE : &str = "~/traps-image-store.toml";

// ***************************************************************************
//                            Structs and Enums
// ***************************************************************************
#[allow(dead_code)]
#[derive(Debug, PartialEq, Eq, Clone)]
pub enum StoreAction {
    Delete,
    ErrorOut,
    Noop,
    ReduceSave,
    Save,
}

#[derive(Debug)]
pub struct StoreParms {
    pub config_file: String,
    pub config: StoreConfig,
}

#[derive(Debug)]
pub struct StoreConfig {
    pub action_thresholds: Vec<(f32, StoreAction)>,
}

#[derive(Debug, Deserialize)]
struct StoreInput {
    pub action_thresholds: BTreeMap<String, f32>,
}

pub struct ImageStorePlugin {
    name: String,
    id: Uuid,
    runctx: &'static RuntimeCtx,
}

// ***************************************************************************
//                                Functions
// ***************************************************************************
impl Plugin for ImageStorePlugin {
    // ---------------------------------------------------------------------------
    // start:
    // ---------------------------------------------------------------------------
    /// The entry point for the plugin. The engine will start the plugin in its own
    /// thread and execute this function.  The pub_socket is used by the plugin to 
    /// publish new events.  The sub_socket is used by the plugin to get events 
    /// published by other plugins.
    fn start(
        &self,
        pub_socket: Socket,
        sub_socket: Socket,
    ) -> Result<(), EngineError> {

        // Announce our arrival.
        info!("{}", format!("{}", Errors::PluginStarted(self.name.clone(), self.get_id().hyphenated().to_string())));

        // Read the configuration file.
        let store_parms = match self.init_store_parms() {
            Ok(a) => a,
            Err(e) => {
                return Err(EngineError::PluginExecutionError(self.name.clone(), 
                                                             self.get_id().hyphenated().to_string(), 
                                                             e.to_string()));
            }
        };

        // Get this plugin's required action function pointer.
        #[allow(unused_variables)]
        let action = match select_action(&self.runctx.parms.config) {
            Ok(a) => a,
            Err(e) => {
                return Err(EngineError::PluginExecutionError(self.name.clone(), 
                                                             self.get_id().hyphenated().to_string(), 
                                                             e.to_string()));
            }
        };

        // Send the plugin start up event.
        match traps_utils::send_started_event(self, &pub_socket) {
            Ok(_) => (),
            Err(e) => return Err(e),
        };

        // Enter our infinite work loop.
        loop {
            // ----------------- Wait on the Next Event -----------------------
            // The bytes vector is an output parameter populated by the marshalling function 
            // with raw event bytes. The ev_in.gen_event field references these raw bytes
            // so the bytes vector must must of a lifetime at least as long as ev_in.
            //
            // The marshalling function returns None when the incoming event is unreadable
            // or improperly constructed.  The problem is logged where it occurs and we 
            // simple wait for the next event to arrive.
            let mut bytes: Vec<u8> = vec![];
            let ev_in = match traps_utils::marshal_next_event(self, &sub_socket, &mut bytes) {
                Some(ev) => ev,
                None => continue,
            };

            // ----------------- Process Subscription Events ------------------
            // Process events we expect; log and disregard all others.
            let terminate = match ev_in.prefix_array {
                IMAGE_SCORED_PREFIX => {
                    debug!("\n  -> {} received event {}", self.name, String::from("ImageScoredEvent"));
                    self.send_event(ev_in.gen_event, &pub_socket, action, &store_parms);
                    false
                },
                PLUGIN_TERMINATE_PREFIX => {
                    // Determine whether we are the target of this terminate event. The called method
                    // will return true if this plugin should shutdown.
                    info!("\n  -> {} received event {}", self.name, String::from("PluginTerminateEvent"));
                    traps_utils::process_plugin_terminate_event(ev_in.gen_event, &self.id, &self.name)
                },
                unexpected => {
                    // This should only happen for valid events to which we are not subscribed.
                    // Completely invalid event prefixes are detected above in check_event_prefix().
                    let pre = format!("{:?}", unexpected);
                    error!("{}", Errors::EventNotHandledError(self.name.clone(), pre));
                    false
                }
            };
        
            // Determine if we should terminate our event read loop.
            if terminate {
                // Clean up and send the terminating event.
                traps_utils::send_terminating_event(&self.name, self.id, &pub_socket);
                break;
            }
        }

        // Shutting down.
        Ok(())
    }

    /// Return the event subscriptions, as a vector of strings, that this plugin is interested in.
    fn get_subscriptions(&self) -> Result<Vec<Box<dyn EventType>>, EngineError> {
        Ok(vec![
            Box::new(events::ImageScoredEvent::new(Uuid::new_v4(), "fake".to_string(), vec![])),
            Box::new(events::PluginTerminateEvent::new(Uuid::new_v4(), String::from("*"))),
        ])
    }

    /// Simple accessors for this plugin.
    fn get_name(&self) -> String {self.name.clone()}
    fn get_id(&self) -> Uuid {self.id}
}

impl ImageStorePlugin {
    // ---------------------------------------------------------------------------
    // new:
    // ---------------------------------------------------------------------------
    pub fn new(runctx: &'static RuntimeCtx) -> Self {
        ImageStorePlugin {
            name: "ImageStorePlugin".to_string(),
            id: Uuid::new_v4(),
            runctx,
        }
    }

    // ---------------------------------------------------------------------------
    // get_runctx:
    // ---------------------------------------------------------------------------
    #[allow(unused)]
    pub fn get_runctx(&self) -> &RuntimeCtx {self.runctx}
    
    // ---------------------------------------------------------------------------
    // send_event:
    // ---------------------------------------------------------------------------
    fn send_event(&self, event: gen_events::Event, pub_socket: &Socket,
                  action: fn(&ImageStorePlugin, &gen_events::ImageScoredEvent, &StoreParms)->StoreAction,
                  store_parms_ref: &StoreParms) {
        // Extract the image uuid from the new image event.
        let image_scored_event = match event.event_as_image_scored_event() {
            Some(ev) => ev,
            None => {
                // Log the error and just return.
                error!("{}", "event_as_new_image_event deserialize error".to_string());
                return
            }
        };
        let uuid_str = match image_scored_event.image_uuid() {
            Some(s) => s,
            None => {
                // Log the error and just return.
                error!("{}", "uuid access error".to_string());
                return
            }
        };
        let uuid = match Uuid::parse_str(uuid_str){
            Ok(u) => u,
            Err(e) => {
                // Log the error and just return.
                error!("{}", e.to_string());
                return
            }
        };

        // Determine the destination based on the first score.
        let labels= match image_scored_event.scores() {
            Some(v) => v,
            None => {
                // Log the error and just return.
                error!("{}", "uuid access error".to_string());
                return
            }
        };

        let image_format = match image_scored_event.image_format() {
            Some(s) => s,
            None => {
                // Log the error and just return.
                let msg = format!("{}", Errors::PluginEventAccessUuidError(
                                          self.get_name(), "ImageScoredEvent".to_string()));
                error!("{}", msg);
                return
            }
        };

        // Make sure we got at least one score.
        if labels.is_empty() {
            error!("{}", "No scores received".to_string());
            return
        }

        // Execute the action function and abort image on error.
        let action_taken = action(self, &image_scored_event, store_parms_ref);
        if action_taken == StoreAction::ErrorOut {
            let msg = format!("{}", Errors::PluginEventActionError(
                                      self.get_name(), "NewImageEvent".to_string(), uuid_str.to_string()));
            error!("{}", msg);
            return
        }

        // Did we decide to delete or store this image?
        let ev: Box<dyn Event>;
        let ev_name: &str;
        if action_taken == StoreAction::Delete {
            // Send an image delete event.
            ev_name = "ImageDeletedEvent";
            ev = Box::new(events::ImageDeletedEvent::new(uuid, image_format.to_string()));
        } else {
            // Create the image stored event and serialize it.
            let dest = format!("{:?}", action_taken);
            ev_name = "ImageStoredEvent";
            ev = Box::new(events::ImageStoredEvent::new(uuid, image_format.to_string(), dest));
        }

        // Convert to a byte stream.
        let bytes = match ev.to_bytes() {
            Ok(v) => v,
            Err(e) => {
                // Log the error and just return.
                error!("{}", e.to_string());
                return
            } 
        };

        // Publish the event.
        // Send the event serialization succeeded.
        match pub_socket.send(bytes, 0) {
            Ok(_) => (),
            Err(e) => {
                // Log the error and abort if we can't send our start up message.
                let msg = format!("{}", Errors::SocketSendError(self.get_name(), ev_name.to_string(), e.to_string()));
                error!("{}", msg);
            }
        };
    }

    // ---------------------------------------------------------------------------
    // init_store_parms:
    // ---------------------------------------------------------------------------
    /** Retrieve the application parameters from the configuration file specified
     * either through an environment variable or as the first (and only) command
     * line argument.  If neither are provided, an attempt is made to use the
     * default file path.
     */
    pub fn init_store_parms(&self) -> Result<StoreParms> {
        // Get the config file path from the environment, command line or default.
        let config_file = env::var(ENV_CONFIG_FILE_KEY).unwrap_or_else(|_| DEFAULT_CONFIG_FILE.to_string());

        // Read the cofiguration file.
        let config_file_abs = traps_utils::get_absolute_path(&config_file);
        // println!("{}", Errors::ReadingConfigFile(config_file_abs.clone()));
        let contents = match fs::read_to_string(&config_file_abs) {
            Ok(c) => c,
            Err(e) => return Result::Err(anyhow!(e.to_string())),
        };

        // Parse the toml configuration.
        let raw_input : StoreInput = match toml::from_str(&contents) {
            Ok(c)  => c,
            Err(e) => return Result::Err(anyhow!(e.to_string())),
        };

        // Create the mutable list into which we'll write the threshold tuples.
        let mut list: Vec<(f32, StoreAction)> = Vec::new();
        if !raw_input.action_thresholds.is_empty() {
            // Iterator through all configured thresholds allowing for
            // some case insensitivity.
            for entry in &raw_input.action_thresholds {
                let act = match entry.0.as_str() {
                    "Delete"     => StoreAction::Delete,
                    "Save"       => StoreAction::Save,
                    "ReduceSave" => StoreAction::ReduceSave,
                    "Noop"       => StoreAction::Noop,
                    "delete"     => StoreAction::Delete,
                    "save"       => StoreAction::Save,
                    "reducesave" => StoreAction::ReduceSave,
                    "noop"       => StoreAction::Noop,
                    &_           => return Result::Err(anyhow!("Invalid store action configured for image_store_plugin".to_string())),
                };

                // Add the new tuple to the list unless
                // it's a noop, which we ignore.
                if act != StoreAction::Noop {
                    let prob = *entry.1;
                    if !(0.0..=1.0).contains(&prob) {
                        return Result::Err(anyhow!("Invalid store threshold: {}. Thesholds must be between 0.0 and 1.0, inclusive.", prob));
                    }
                    list.push((prob, act));
                }
            }
        } 

        // Make sure we have the whole confidence range of 0.0-1.0 covered.
        // Threshold semantics are, "If the score is greater than or equal
        // to the entry number, then perform the associated store action."
        // If no 0.0 entry number was specified, we insert a delete action
        // entry by default.
        let mut found_zero = false;
        for entry in &list {
            if entry.0 == 0.0 {
                found_zero = true;
                break;
            }
        }
        if !found_zero{
            list.push((0.0, StoreAction::Delete));
        }
        
        // Sort the list in descending order of numerical values.
        // a.partial_cmp(b) yields ascending order, b.partial_cmp(a) 
        // descending. We use the stable sort so as to not reorder tuples 
        // with the same numeric value, which we tolerate on input but is 
        // sloppy on the part of users (only the first one has an effect).
        // For some reason, clippy says (&b.0) is an unnecessary borrow.
        list.sort_by(|a, b| (b.0).partial_cmp(&a.0).expect("failed f32 compare!"));

        // Convert the u8 element to f32 to match the scoring type.
        let mut listf32: Vec<(f32, StoreAction)> = Vec::new();
        let it = list.iter().map(|cur| (cur.0 as f32, cur.1.clone()));
        for item in it {
            listf32.push(item);
        }

        // Return a newly constructed storage parms object.
        Result::Ok(StoreParms { config_file: config_file_abs, config: StoreConfig {action_thresholds: listf32} })
    }

}


#[cfg(test)]
mod tests {
    use crate::plugins::image_store_plugin::StoreAction;
    use crate::events::{ImageLabelScore, ImageScoredEvent};
    use uuid::Uuid;
    use serde_json;

    #[test]
    fn here_i_am() {
        println!("file test: image_store_plugin.rs");
    }

    #[test]
    fn ordtest() {
        let mut list: Vec<(f32, StoreAction)> = Vec::new();
        list.push((0.25,   StoreAction::ReduceSave));
        list.push((0.15,   StoreAction::Delete));
        list.push((0.15,   StoreAction::Noop));
        list.push((0.5,    StoreAction::Save));
        list.push((0.0,    StoreAction::Delete));
        list.push((0.45,   StoreAction::Save));
        list.push((0.3567, StoreAction::Noop));

        // Assert original order.
        // println!("{}", "Before sort");
        // for entry in &list {
        //     println!("{} {:?}", entry.0, entry.1);
        // }
        assert_eq!(&list[0], &(0.25,   StoreAction::ReduceSave));
        assert_eq!(&list[1], &(0.15,   StoreAction::Delete));
        assert_eq!(&list[2], &(0.15,   StoreAction::Noop));
        assert_eq!(&list[3], &(0.5,    StoreAction::Save));
        assert_eq!(&list[4], &(0.0,    StoreAction::Delete));
        assert_eq!(&list[5], &(0.45,   StoreAction::Save));
        assert_eq!(&list[6], &(0.3567, StoreAction::Noop));

        // Reorder list in descending order of first tuple element.
        // This should be the same code that we use in init_store_parms()
        // to order the thresholds read in from the configuration file. 
        list.sort_by(|a, b| (&b.0).partial_cmp(&a.0).expect("failed f32 compare!"));

        // Assert sorted order.
        // println!("\n{}", "After sort");
        // for entry in &list {
        //     println!("{} {:?}", entry.0, entry.1);
        // }
        assert_eq!(&list[0], &(0.5,    StoreAction::Save));
        assert_eq!(&list[1], &(0.45,   StoreAction::Save));
        assert_eq!(&list[2], &(0.3567, StoreAction::Noop));
        assert_eq!(&list[3], &(0.25,   StoreAction::ReduceSave));
        assert_eq!(&list[4], &(0.15,   StoreAction::Delete));
        assert_eq!(&list[5], &(0.15,   StoreAction::Noop));
        assert_eq!(&list[6], &(0.0,    StoreAction::Delete));
    }

    #[test]
    fn sertest() {
        // Image uuid.
        let uuid = Uuid::new_v4();
        
        // Create label vector.
        let label1 = ImageLabelScore::new(uuid.clone(), "cow".to_string(), 0.8); 
        let label2 = ImageLabelScore::new(uuid.clone(), "dog".to_string(), 0.3); 
        let labels:Vec<ImageLabelScore> = vec!(label1, label2);

        // Create the event.
        let ev = ImageScoredEvent::new(uuid.clone(), "png".to_string(), labels);

        // Serialize event to json.
        let json_str = serde_json::to_string(&ev).unwrap();
        println!("{}", json_str); // assert is difficult because of timestamp.
    }

}
