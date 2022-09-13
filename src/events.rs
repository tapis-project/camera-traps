use uuid::Uuid;
use event_engine::events::{Event, EventType};
use event_engine::errors::EngineError;
use flatbuffers::{FlatBufferBuilder, InvalidFlatbuffer};
use std::error::Error;

// Logging imports.
use anyhow::Result;

// Application errors.
use crate::config::errors::Errors;
use crate::events_generated::gen_events;
use crate::traps_utils::timestamp_str;

// ***************************************************************************
// EVENTS
// ***************************************************************************
// ---------------------------------------------------------------------------
// NewImageEvent:
// ---------------------------------------------------------------------------
pub struct NewImageEvent {
    created: String,
    image_uuid: Uuid,
    image_format: String,
    image: Vec<u8>,
}

// ------ Implement EventType
impl EventType for NewImageEvent {
    fn get_name(&self) -> String {
        String::from("NewImageEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        // just return the bytes associated with the name.
        Ok(self.get_name().as_bytes().to_vec())
    }
}

// ------ Implement Event
impl Event for NewImageEvent {
    /// convert the event to a raw byte array
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::NewImageEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.to_hyphenated().to_string())),
            image_format: Some(fbuf.create_string(&self.image_format)),
            image: Some(fbuf.create_vector(&self.image)),
        };
        let event_offset = gen_events::NewImageEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::NewImageEvent,
            event: Some(event_offset.as_union_value()),
        };
        let union_offset = gen_events::Event::create(&mut fbuf, &union_args);

        // Complete the flatbuffer and extract its data as a byte array.
        fbuf.finish(union_offset, None);
        let bytes = fbuf.finished_data();

        // Copy the raw data into a properly sized vector.
        let mut byte_vec: Vec<u8> = Vec::with_capacity(bytes.len());
        byte_vec.extend_from_slice(bytes);
        Ok(byte_vec)
    }

    /// Get a NewImageEvent from a vector raw event bytes.
    fn from_bytes(bytes: Vec<u8>) -> Result<NewImageEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "NewImageEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_new_image_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        let event_object = NewImageEvent::new_from_gen(flatbuf_event);
        Result::Ok(event_object)
    }
}

// ------ Implement Status Functions
impl NewImageEvent {
    #![allow(unused)]
    pub fn new(image_uuid: Uuid, image_format: String, image: Vec<u8>) -> Self {
        NewImageEvent {
            created: timestamp_str(),
            image_uuid: image_uuid,
            image_format: image_format,
            image: image,
        }
    }

    pub fn new_from_gen(ev: gen_events::NewImageEvent) -> Self {
        // Create and populate the image vector.
        let raw_image = ev.image().unwrap();
        let mut image = Vec::with_capacity(raw_image.len());
        image.extend_from_slice(raw_image);
    
        NewImageEvent {
            created: String::from(ev.event_create_ts().unwrap()),
            image_uuid: Uuid::parse_str(ev.image_uuid().unwrap()).unwrap(),
            image_format: ev.image_format().unwrap().to_string(),
            image: image,
        }
    }

    // pub fn event_from_bytes(bytes: Vec<u8>) -> Result<Box<dyn EventType>, Box<dyn Error>> {

    // }


}

// ---------------------------------------------------------------------------
// ImageDeletedEvent:
// ---------------------------------------------------------------------------
pub struct ImageDeletedEvent {}
impl EventType for ImageDeletedEvent {
    fn get_name(&self) -> String {
        String::from("ImageDeletedEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        // just return the bytes associated with the name.
        Ok(self.get_name().as_bytes().to_vec())
    }
}

// ***************************************************************************
// PRIVATE FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// bytes_to_gen_event:
// ---------------------------------------------------------------------------
/** Givent a reference to a byte array containing the serialized flatbuffer
 * event, convert it into an event as defined in the generated flatbuffer code.
 */
fn bytes_to_gen_event(msg_bytes: &[u8]) -> Result<gen_events::Event, InvalidFlatbuffer> {
    return Result::Ok(gen_events::root_as_event(msg_bytes)?);
}

// ---------------------------------------------------------------------------
// check_event_type:
// ---------------------------------------------------------------------------
/** Make sure the generated event is of the expected type, return an error
 * otherwise.
 */
fn check_event_type(expected: &str, event: &gen_events::Event) -> Result<(), Errors> {
    // Get the event type as a string reference.
    let event_type = match (*event).event_type().variant_name() {
        Some(etype) => etype,
        None => {return Err(Errors::EventReadTypeError(expected.to_string()));}
    };

    // Check that we got the expected event type.
    if expected != event_type {
        return Err(Errors::EventUnexpectedError(expected.to_string(), event_type.to_string())); 
    };

    // Success.
    Ok(())
}



#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: events.rs");
    }
}
