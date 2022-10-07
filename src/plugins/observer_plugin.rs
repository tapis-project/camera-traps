use uuid::Uuid;
use zmq::Socket;
use event_engine::plugins::Plugin;
use event_engine::errors::EngineError;
use event_engine::events::{Event, EventType};
use crate::{events, config::errors::Errors};
use crate::traps_utils;
use crate::Config;
use crate::events::{EVENT_PREFIX_LEN, check_event_prefix, NEW_IMAGE_PREFIX, IMAGE_RECEIVED_PREFIX,
                    IMAGE_SCORED_PREFIX, IMAGE_STORED_PREFIX, IMAGE_DELETED_PREFIX, PLUGIN_STARTED_PREFIX,
                    PLUGIN_TERMINATING_PREFIX, PLUGIN_TERMINATE_PREFIX};

use log::{info, error};

pub struct ObserverPlugin {
    name: String,
    id: Uuid,
    config: &'static Config,
}
impl Plugin for ObserverPlugin {

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

        // Send the plugin start up event.
        match traps_utils::send_started_event(self, &pub_socket) {
            Ok(_) => (),
            Err(e) => return Err(e),
        };

        // Enter our infinite work loop.
        loop {
            // ----------------- Retrieve and Slice Raw Bytes -----------------
            // Wait on the subsciption socket.
            let bytes = match sub_socket.recv_bytes(0) {
                Ok(b) => b,
                Err(e) => {
                    // We log error and then move on. It would probably be a good idea to 
                    // pause before continuing if there are too many errors in a short period
                    // of time.  This would avoid filling up the log file and burning cycles
                    // when things go sideways for a while.
                    error!("{}", Errors::SocketRecvError(self.name.clone(), e.to_string()));
                    continue;
                }
            };

            // Basic buffer length checking to make sure we have
            // the event prefix and at least 1 other byte.
            if bytes.len() < EVENT_PREFIX_LEN + 1 {
                error!("{}", Errors::EventInvalidLen(self.name.clone(), bytes.len()));
                continue;
            }

            // Split the 2 zqm prefix bytes from the flatbuffer bytes.
            let prefix_bytes = &bytes[0..EVENT_PREFIX_LEN];
            let fbuf_bytes = &bytes[EVENT_PREFIX_LEN..];

            // ----------------- Get the FBS Generated Event ------------------
            // Get the generated event and its type.
            let gen_event = match traps_utils::bytes_to_gen_event(fbuf_bytes) {
                Ok(tuple)=> tuple,
                Err(e)=> {
                    error!("{}", e.to_string());
                    continue;
                }
            };

            // Get the event name from the generated event and check it against prefix slice.
            let event_name = match gen_event.event_type().variant_name() {  
                Some(n) => n,
                None => {
                    error!("{}", Errors::EventNoneError(self.name.clone()));
                    continue;
                },
            };

            // ----------------- Check the Prefix and Event -------------------
            // Check that the prefix bytes match the event type. 
            // False means a mismatch was detected and the 
            let prefix_array = [prefix_bytes[0], prefix_bytes[1]];
            if !check_event_prefix(prefix_array, event_name) {
                let pre = format!("{:?}", prefix_array);
                let name = event_name.to_string();
                error!("{}", Errors::EventPrefixMismatch(self.name.clone(), pre, name));
                continue;
            }

            // ----------------- Process Subscription Events ------------------
            // Process events we expect; log and disregard all others.
            let terminate = match prefix_array {
                NEW_IMAGE_PREFIX => {
                    self.record_event("NewImageEvent");
                    false
                },
                IMAGE_RECEIVED_PREFIX => {
                    self.record_event("ImageReceivedEvent");
                    false
                },
                IMAGE_SCORED_PREFIX => {
                    self.record_event("ImageScoredEvent");
                    false
                },
                IMAGE_STORED_PREFIX => {
                    self.record_event("ImageStoredEvent");
                    false
                },
                IMAGE_DELETED_PREFIX => {
                    self.record_event("ImageDeletedEvent");
                    false
                },
                PLUGIN_STARTED_PREFIX => {
                    self.record_event("PluginStartedEvent");
                    false
                },
                PLUGIN_TERMINATING_PREFIX => {
                    self.record_event("PluginTerminatingEvent");
                    false
                },
                PLUGIN_TERMINATE_PREFIX => {
                    // Determine whether we are the target of this terminate event. The called method
                    // will return true if this plugin should shutdown.
                    self.record_event("PluginTerminateEvent");
                    traps_utils::process_plugin_terminate_event(gen_event, &self.id, &self.name)
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

    /// Return the event subscriptions as a vector of event types that this plugin is interested in.
    fn get_subscriptions(&self) -> Result<Vec<Box<dyn EventType>>, EngineError> {
        // This plugin subscribes to all events.  When events change so must this list.
        Ok(vec![
            Box::new(events::NewImageEvent::new(Uuid::new_v4(), String::from("fake"), vec![])),
            Box::new(events::ImageReceivedEvent::new(Uuid::new_v4())),
            Box::new(events::ImageScoredEvent::new(Uuid::new_v4(), vec![])),
            Box::new(events::ImageStoredEvent::new(Uuid::new_v4(), String::from("path"))),
            Box::new(events::ImageDeletedEvent::new(Uuid::new_v4())),
            Box::new(events::PluginTerminateEvent::new(Uuid::new_v4(), String::from("*"))),
            Box::new(events::PluginTerminatingEvent::new(Uuid::new_v4(), String::from("ObserverPlugin"))), 
            Box::new(events::PluginStartedEvent::new(Uuid::new_v4(), String::from("ObserverPlugin"))),
        ])
    }

    /// Simple accessors for this plugin.
    fn get_name(&self) -> String {self.name.clone()}
    fn get_id(&self) -> Uuid {self.id}
}

impl ObserverPlugin {
    pub fn new(config: &'static Config) -> Self {
        ObserverPlugin {
            name: "ObserverPlugin".to_string(),
            id: Uuid::new_v4(),
            config,
        }
    }

    // Just log receiving the event.
    fn record_event(&self, event_name: &str) {
        info!("\n  -> {} received event {}", self.name, String::from(event_name));
    }
}


#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: observer.rs");
    }
}
