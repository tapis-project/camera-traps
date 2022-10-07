use uuid::Uuid;
use zmq::Socket;
use event_engine::{plugins::Plugin, events::Event};
use event_engine::errors::EngineError;
use event_engine::events::EventType;
use crate::{events, config::errors::Errors};
use crate::traps_utils;
use crate::Config;
use crate::events::{EVENT_PREFIX_LEN, check_event_prefix, PLUGIN_TERMINATE_PREFIX};

use log::{info, error};
use std::{thread, time};

pub struct ImageGenPlugin {
    name: String,
    id: Uuid,
    config: &'static Config,
}

impl Plugin for ImageGenPlugin {

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

        // Send optional test events. 
        if self.config.plugins.run_gen_driver.expect("Config.run_gen_driver was not a valid bool!") {
            self.run_test_driver(&pub_socket);
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

            // Process events we expect; log and disregard all others.
            let terminate = match prefix_array {
                PLUGIN_TERMINATE_PREFIX => {
                    // Determine whether we are the target of this terminate event.
                    info!("{}", format!("{}", Errors::EventProcessing(self.name.clone(), "PluginTerminateEvent")));
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

    /// Return the event subscriptions, as a vector of strings, that this plugin is interested in.
    fn get_subscriptions(&self) -> Result<Vec<Box<dyn EventType>>, EngineError> {
        Ok(vec![Box::new(events::PluginTerminateEvent::new(Uuid::new_v4(), String::from("*")))])
    }

    /// Simple accessors for this plugin.
    fn get_name(&self) -> String {self.name.clone()}
    fn get_id(&self) -> Uuid {self.id}
}

impl ImageGenPlugin {
    pub fn new(config:&'static Config) -> Self {
        ImageGenPlugin {
            name: "ImageGenPlugin".to_string(),
            id: Uuid::new_v4(),
            config,
        }
    }

    fn run_test_driver(&self, pub_socket: &Socket) {

        thread::sleep(time::Duration::new(3, 0));
        info!("{}", "---------------- run_test_driver Waking UP!");

        // Create event.
        let ev = events::ImageReceivedEvent::new(Uuid::new_v4());
        let bytes = match ev.to_bytes() {
            Ok(v) => v,
            Err(e) => {
                // Log the error and just return.
                let msg = format!("{}", Errors::EventToBytesError(self.name.clone(), ev.get_name(), e.to_string()));
                error!("{}", msg);
                return
            } 
        };

        // Send the event.
        match pub_socket.send(bytes, 0) {
            Ok(_) => (),
            Err(e) => {
                // Log the error and abort if we can't send our start up message.
                let msg = format!("{}", Errors::SocketSendError(self.name.clone(), ev.get_name(), e.to_string()));
                error!("{}", msg);
            }
        };
    }
}

#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: image_gen_plugin.rs");
    }
}
