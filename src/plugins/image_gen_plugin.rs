use uuid::Uuid;
use zmq::Socket;
use event_engine::{plugins::Plugin};
use event_engine::errors::EngineError;
use event_engine::events::EventType;
use crate::{events, config::errors::Errors};
use crate::traps_utils;
use crate::events::{PLUGIN_TERMINATE_PREFIX};
use crate::plugins::actions::image_gen_actions::select_action;
use crate::RuntimeCtx;

use log::{info, error};

pub struct ImageGenPlugin {
    name: String,
    id: Uuid,
    runctx: &'static RuntimeCtx,
}

impl Plugin for ImageGenPlugin {
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

            // Process events we expect; log and disregard all others.
            let terminate = match ev_in.prefix_array {
                PLUGIN_TERMINATE_PREFIX => {
                    // Determine whether we are the target of this terminate event.
                    info!("{}", format!("{}", Errors::EventProcessing(self.name.clone(), "PluginTerminateEvent")));
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
        Ok(vec![Box::new(events::PluginTerminateEvent::new(Uuid::new_v4(), String::from("*")))])
    }

    /// Simple accessors for this plugin.
    fn get_name(&self) -> String {self.name.clone()}
    fn get_id(&self) -> Uuid {self.id}
}

impl ImageGenPlugin {
    
    // ---------------------------------------------------------------------------
    // new:
    // ---------------------------------------------------------------------------
    pub fn new(runctx: &'static RuntimeCtx) -> Self {
        ImageGenPlugin {
            name: "ImageGenPlugin".to_string(),
            id: Uuid::new_v4(),
            runctx,
        }
    }

    // ---------------------------------------------------------------------------
    // get_runctx:
    // ---------------------------------------------------------------------------
    #[allow(unused)]
    pub fn get_runctx(&self) -> &RuntimeCtx {self.runctx}
}


#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: image_gen_plugin.rs");
    }
}
