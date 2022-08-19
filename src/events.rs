use event_engine::events::{EventType, Event};
use event_engine::errors::EngineError;

pub struct ImageDeletedEvent {}
impl EventType for ImageDeletedEvent {
    fn get_name(&self) -> String {
        let s = "ImageDeletedEvent";
        s.to_string()
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        // just return the bytes associated with the name.
        Ok(self.get_name().as_bytes().to_vec())
    }
}

#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: events.rs");
    }
}
