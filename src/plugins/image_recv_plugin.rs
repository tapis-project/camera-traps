use uuid::Uuid;
use zmq::Socket;
use event_engine::{plugins::Plugin};
use event_engine::errors::EngineError;
use event_engine::events::EventType;
use event_engine::events::Event;
use crate::events_generated::gen_events;
use crate::{events, config::errors::Errors};
use crate::{traps_utils, RuntimeCtx};
use crate::events::{NEW_IMAGE_PREFIX, PLUGIN_TERMINATE_PREFIX};
use crate::plugins::actions::image_recv_actions::select_action;

use log::{info, error, debug};


pub struct ImageReceivePlugin {
    name: String,
    id: Uuid,
    runctx: &'static RuntimeCtx,
}

impl Plugin for ImageReceivePlugin {
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
                NEW_IMAGE_PREFIX => {
                    debug!("\n  -> {} received event {}", self.name, String::from("NewImageEvent"));
                    self.send_event(ev_in.gen_event, &pub_socket, action);
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
            Box::new(events::NewImageEvent::new(Uuid::new_v4(), String::from("fake"), vec![])),
            Box::new(events::PluginTerminateEvent::new(Uuid::new_v4(), String::from("*"))),
        ])
    }

    /// Simple accessors for this plugin.
    fn get_name(&self) -> String {self.name.clone()}
    fn get_id(&self) -> Uuid {self.id}
}

impl ImageReceivePlugin {

    // ---------------------------------------------------------------------------
    // new:
    // ---------------------------------------------------------------------------
    pub fn new(runctx: &'static RuntimeCtx) -> Self {
        ImageReceivePlugin {
            name: "ImageReceivePlugin".to_string(),
            id: Uuid::new_v4(),
            runctx,
        }
    }

    // ---------------------------------------------------------------------------
    // get_runctx:
    // ---------------------------------------------------------------------------
    pub fn get_runctx(&self) -> &RuntimeCtx {self.runctx}

    // ---------------------------------------------------------------------------
    // send_event:
    // ---------------------------------------------------------------------------
    fn send_event(&self, event: gen_events::Event, pub_socket: &Socket, 
                  action: fn(&ImageReceivePlugin, &gen_events::NewImageEvent) -> bool) {
        // Extract the image uuid from the new image event.
        let new_image_event = match event.event_as_new_image_event() {
            Some(ev) => ev,
            None => {
                // Log the error and just return.
                let msg = format!("{}", Errors::PluginEventDeserializationError(
                                        self.get_name(), "NewImageEvent".to_string()));
                error!("{}", msg);
                return
            }
        };
        let uuid_str = match new_image_event.image_uuid() {
            Some(s) => s,
            None => {
                // Log the error and just return.
                let msg = format!("{}", Errors::PluginEventAccessUuidError(
                                          self.get_name(), "NewImageEvent".to_string()));
                error!("{}", msg);
                return
            }
        };
        let uuid = match Uuid::parse_str(uuid_str){
            Ok(u) => u,
            Err(e) => {
                // Log the error and just return.
                let msg = format!("{}", Errors::PluginEventParseUuidError(
                                          self.get_name(), "NewImageEvent".to_string(), e.to_string()));
                error!("{}", msg);
                return
            }
        };

        let image_format = match new_image_event.image_format() {
            Some(s) => s,
            None => {
                // Log the error and just return.
                let msg = format!("{}", Errors::PluginEventAccessUuidError(
                                          self.get_name(), "NewImageEvent".to_string()));
                error!("{}", msg);
                return
            }
        };

        // Execute the action function.  False is returned by actions if they are 
        // unable to complete their tasks and processing for this event should abort. 
        if !action(self, &new_image_event) {
            let msg = format!("{}", Errors::PluginEventActionError(
                                      self.get_name(), "NewImageEvent".to_string(), uuid_str.to_string()));
            error!("{}", msg);
            return
        }

        // Create the image received event and serialize it.
        let ev = events::ImageReceivedEvent::new(uuid, image_format.to_string());
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
                // Log the error and return if we can't send the message.
                let msg = format!("{}", Errors::SocketSendError(self.get_name(), ev.get_name(), e.to_string()));
                error!("{}", msg);
            }
        };
    }

}


#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: image_recv_plugin.rs");
    }
}
