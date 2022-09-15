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
// ===========================================================================
// NewImageEvent:
// ===========================================================================
pub struct NewImageEvent {
    created: String,
    image_uuid: Uuid,
    image_format: String,
    image: Vec<u8>,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for NewImageEvent {
    fn get_name(&self) -> String {
        String::from("NewImageEvent")
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for NewImageEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
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

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
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
        match NewImageEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl NewImageEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(image_uuid: Uuid, image_format: String, image: Vec<u8>) -> Self {
        NewImageEvent {
            created: timestamp_str(),
            image_uuid: image_uuid,
            image_format: image_format,
            image: image,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::NewImageEvent) -> Result<Self, Errors> {
        // Create and populate the image vector.
        let raw = match ev.image() {
            Some(raw) => raw,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("image")))},
        };
        let mut image = Vec::with_capacity(raw.len());
        image.extend_from_slice(raw);

        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("created")))},
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("image_uuid"), e.to_string()))},
        };

        // Get the image format string.
        let format = match ev.image_format() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("image_format")))},
        };
    
        // Finally...
        Result::Ok(NewImageEvent {
            created: String::from(created),
            image_uuid: uuid,
            image_format: String::from(format),
            image: image,
        })
    }
}

// ===========================================================================
// ImageRecievedEvent:
// ===========================================================================
pub struct ImageReceivedEvent {
    created: String,
    image_uuid: Uuid,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageReceivedEvent {
    fn get_name(&self) -> String {
        String::from("ImageReceivedEvent")
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageReceivedEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::ImageReceivedEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.to_hyphenated().to_string())),
        };
        let event_offset = gen_events::ImageReceivedEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::ImageReceivedEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageReceivedEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageReceivedEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_received_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageReceivedEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl ImageReceivedEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(image_uuid: Uuid) -> Self {
        ImageReceivedEvent {
            created: timestamp_str(),
            image_uuid: image_uuid,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::ImageReceivedEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("created")))},
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("image_uuid"), e.to_string()))},
        };

        // Finally...
        Result::Ok(ImageReceivedEvent {
            created: String::from(created),
            image_uuid: uuid,
        })
    }
}

// ===========================================================================
// ImageScoredEvent:
// ===========================================================================
pub struct ImageScoredEvent {
    created: String,
    image_uuid: Uuid,
    scores: [ImageLabelScore],
}

pub struct ImageLabelScore {
    image_uuid: Uuid,
    label: String,
    probability: f32,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageScoredEvent {
    fn get_name(&self) -> String {
        String::from("ImageScoredEvent")
    }
}

// ===========================================================================
// ImageStoredEvent:
// ===========================================================================
pub struct ImageStoredEvent {
    created: String,
    image_uuid: Uuid,
    destination: String,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageStoredEvent {
    fn get_name(&self) -> String {
        String::from("ImageStoredEvent")
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageStoredEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::ImageStoredEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.to_hyphenated().to_string())),
            destination: Some(fbuf.create_string(&self.destination)),
        };
        let event_offset = gen_events::ImageStoredEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::ImageStoredEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageStoredEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageStoredEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_stored_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageStoredEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl ImageStoredEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(image_uuid: Uuid, destination: String) -> Self {
        ImageStoredEvent {
            created: timestamp_str(),
            image_uuid: image_uuid,
            destination: destination,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::ImageStoredEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("created")))},
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("image_uuid"), e.to_string()))},
        };

        // Get the destination.
        let destination = match ev.destination() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("destination")))},
        };

        // Finally...
        Result::Ok(ImageStoredEvent {
            created: String::from(created),
            image_uuid: uuid,
            destination: String::from(destination),
        })
    }
}

// ===========================================================================
// ImageDeletedEvent:
// ===========================================================================
pub struct ImageDeletedEvent {
    created: String,
    image_uuid: Uuid,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageDeletedEvent {
    fn get_name(&self) -> String {
        String::from("ImageDeletedEvent")
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageDeletedEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::ImageDeletedEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.to_hyphenated().to_string())),
        };
        let event_offset = gen_events::ImageDeletedEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::ImageDeletedEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageDeletedEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageDeletedEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_deleted_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageDeletedEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl ImageDeletedEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(image_uuid: Uuid) -> Self {
        ImageDeletedEvent {
            created: timestamp_str(),
            image_uuid: image_uuid,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::ImageDeletedEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("created")))},
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("image_uuid"), e.to_string()))},
        };

        // Finally...
        Result::Ok(ImageDeletedEvent {
            created: String::from(created),
            image_uuid: uuid,
        })
    }
}

// ===========================================================================
// PluginStartedEvent:
// ===========================================================================
pub struct PluginStartedEvent {
    created: String,
    plugin_name: String,
    plugin_uuid: Uuid,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for PluginStartedEvent {
    fn get_name(&self) -> String {
        String::from("PluginStartedEvent")
    }
}

// ===========================================================================
// PluginTerminateEvent:
// ===========================================================================
pub struct PluginTerminateEvent {
    created: String,
    target_plugin_name: String,
    target_plugin_uuid: Uuid,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for PluginTerminateEvent {
    fn get_name(&self) -> String {
        String::from("PluginTerminateEvent")
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

// ---------------------------------------------------------------------------
// serialize_flatbuffer:
// ---------------------------------------------------------------------------
fn serialize_flatbuffer(mut fbuf: FlatBufferBuilder, union_args: gen_events::EventArgs) -> Vec<u8> {
    // Get the offset of the particular event already encoded in the union argument.    
    let union_offset = gen_events::Event::create(&mut fbuf, &union_args);
    
    // Complete the flatbuffer and extract its data as a byte array.
    fbuf.finish(union_offset, None);
    let bytes = fbuf.finished_data();

    // Copy the raw data into a properly sized vector.
    let mut byte_vec: Vec<u8> = Vec::with_capacity(bytes.len());
    byte_vec.extend_from_slice(bytes);
    byte_vec
}

// ***************************************************************************
// TESTS
// ***************************************************************************
#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: events.rs");
    }
}
