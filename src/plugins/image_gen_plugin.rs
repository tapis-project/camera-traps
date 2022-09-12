use uuid::Uuid;
use zmq::Socket;
use event_engine::plugins::Plugin;
use event_engine::errors::EngineError;
use event_engine::events::EventType;

use crate::events;


struct ImageGenPlugin {
    name: String,
    id: Uuid,
}

impl ImageGenPlugin {
    pub fn new() -> Self {
        ImageGenPlugin {
            name: "ImageGenPlugin".to_string(),
            id: Uuid::new_v4(),
        }
    }
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
        println!(
            "MsgProducer (plugin id {}) start function starting...",
            self.get_id()
        );
        println!(
            "MsgProducer (plugin id {}) finished 1 second sleep",
            self.get_id()
        );

        // Create a new image event.
        //let ev = events::NewImageEvent::new();

        Ok(())
    }

    /// Return the event subscriptions, as a vector of strings, that this plugin is interested in.
    fn get_subscriptions(&self) -> Result<Vec<Box<dyn EventType>>, EngineError> {
        // ***** TEMP
        Err(EngineError::PubSocketTCPBindError{0: "xx".to_string()})
    }

    /// Returns the unique id for this plugin.
    fn get_id(&self) -> Uuid {
        self.id
    }
}


#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: image_gen_plugin.rs");
    }
}
