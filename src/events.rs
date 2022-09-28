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
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
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
            image_uuid,
            image_format,
            image,
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
            image,
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
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
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
            image_uuid,
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
// ------------------------------
// ------ ImageLabelScore
// ------------------------------
pub struct ImageLabelScore {
    image_uuid: Uuid,
    label: String,
    probability: f32,
}

impl ImageLabelScore {
    #![allow(unused)]
    pub fn new(image_uuid: Uuid, label: String, probability: f32) -> Self {
        ImageLabelScore {
            image_uuid,
            label,
            probability,
        }
    }

    pub fn new_from_gen(ev: gen_events::ImageLabelScore) -> Result<Self, Errors> {
        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("image_uuid"), e.to_string()))},
        };

        // Get the image label string.
        let label = match ev.label() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("label")))},
        };

        // Get the label's probability value.
        let probability = ev.probability(); 
        
        // Return the object.
        Result::Ok(ImageLabelScore {
            image_uuid: uuid,
            label: String::from(label),
            probability,
        })
    }
}

// ------------------------------
// ------ ImageScoredEvent
// ------------------------------
pub struct ImageScoredEvent {
    created: String,
    image_uuid: Uuid,
    scores: Vec<ImageLabelScore>,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageScoredEvent {
    fn get_name(&self) -> String {
        String::from("ImageScoredEvent")
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageScoredEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Create a vector of gen_events::ImageLabelScores from this object's scores.
        // First create a vector to hold the gen_events::ImageLabelScore objects.
        let mut image_label_scores = Vec::<flatbuffers::WIPOffset<gen_events::ImageLabelScore>>::new();
        for score in &self.scores {
            // Assign the string fields.
            let image_uuid = Some(fbuf.create_string(&score.image_uuid.hyphenated().to_string()));
            let label = Some(fbuf.create_string(&score.label));

            // Create each generated score object 
            let im_score = gen_events::ImageLabelScore::create(
                &mut fbuf,
                &gen_events::ImageLabelScoreArgs {
                    image_uuid,
                    label,
                    probability: score.probability,
                },
            );
            // Add the current generated score object to the list.
            image_label_scores.push(im_score);
        }

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::ImageScoredEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
            scores: Some(fbuf.create_vector(&image_label_scores)),
        };
        let event_offset = gen_events::ImageScoredEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::ImageScoredEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageScoredEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageScoredEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_scored_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageScoredEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl ImageScoredEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(image_uuid: Uuid, scores: Vec<ImageLabelScore>) -> Self {
        ImageScoredEvent {
            created: timestamp_str(),
            image_uuid,
            scores,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::ImageScoredEvent) -> Result<Self, Errors> {
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

        // Get the list of scores.
        let gen_scores = match ev.scores() {
            Some(v) => v,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("scores"))),
        };

        // Iterate through each generated score and add to list of event scores.
        let mut scores: Vec<ImageLabelScore> = Vec::new();
        for gen_score in gen_scores {
            // Extract the imaget uuid.
            let u = match gen_score.image_uuid() {
                Some(u) => u,
                None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("ImageLabelScore.image_uuid")))},
            };
            let image_uuid = match Uuid::parse_str(u) {
                Ok(u) => u,
                Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("ImageLabelScore.image_uuid"), e.to_string()))},
            };

            // Extract the label.
            let label = match gen_score.label() {
                Some(s)=> s,
                None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("ImageLabelScore.label")))},
            };
            
            // Extract the probability.
            let probability = gen_score.probability();

            // Create the event imagelabelscore and add it to the vector.
            let new_score = ImageLabelScore {
                image_uuid,
                label: label.to_string(),
                probability,
            };
            scores.push(new_score);
        }

        // Finally...
        Result::Ok(ImageScoredEvent {
            created: String::from(created),
            image_uuid: uuid,
            scores,
        })
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
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
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
            image_uuid,
            destination,
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
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
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
            image_uuid,
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

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for PluginStartedEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::PluginStartedEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            plugin_name: Some(fbuf.create_string(&self.plugin_name)),
            plugin_uuid: Some(fbuf.create_string(&self.plugin_uuid.hyphenated().to_string())),
        };
        let event_offset = gen_events::PluginStartedEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::PluginStartedEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
    fn from_bytes(bytes: Vec<u8>) -> Result<PluginStartedEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "PluginStartedEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_plugin_started_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match PluginStartedEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl PluginStartedEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(plugin_uuid: Uuid, plugin_name: String) -> Self {
        PluginStartedEvent {
            created: timestamp_str(),
            plugin_name,
            plugin_uuid,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::PluginStartedEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("created")))},
        };

        // Get the plugin_name.
        let plugin_name = match ev.plugin_name() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("plugin_name")))},
        };

        // Get the uuid.
        let u = match ev.plugin_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("plugin_uuid"), e.to_string()))},
        };

        // Finally...
        Result::Ok(PluginStartedEvent {
            created: String::from(created),
            plugin_name: String::from(plugin_name),
            plugin_uuid: uuid,
        })
    }
}

// ===========================================================================
// PluginTerminatingEvent:
// ===========================================================================
pub struct PluginTerminatingEvent {
    created: String,
    plugin_name: String,
    plugin_uuid: Uuid,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for PluginTerminatingEvent {
    fn get_name(&self) -> String {
        String::from("PluginTerminatingEvent")
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for PluginTerminatingEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::PluginTerminatingEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            plugin_name: Some(fbuf.create_string(&self.plugin_name)),
            plugin_uuid: Some(fbuf.create_string(&self.plugin_uuid.hyphenated().to_string())),
        };
        let event_offset = gen_events::PluginTerminatingEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::PluginTerminatingEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
    fn from_bytes(bytes: Vec<u8>) -> Result<PluginTerminatingEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "PluginTerminatingEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_plugin_terminating_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match PluginTerminatingEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl PluginTerminatingEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(plugin_uuid: Uuid, plugin_name: String) -> Self {
        PluginTerminatingEvent {
            created: timestamp_str(),
            plugin_name,
            plugin_uuid,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::PluginTerminatingEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("created")))},
        };

        // Get the plugin_name.
        let plugin_name = match ev.plugin_name() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("plugin_name")))},
        };

        // Get the uuid.
        let u = match ev.plugin_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("plugin_uuid"), e.to_string()))},
        };

        // Finally...
        Result::Ok(PluginTerminatingEvent {
            created: String::from(created),
            plugin_name: String::from(plugin_name),
            plugin_uuid: uuid,
        })
    }
}

// ===========================================================================
// PluginTerminateEvent:
// ===========================================================================
pub struct PluginTerminateEvent {
    pub created: String,
    pub target_plugin_name: String,
    pub target_plugin_uuid: Uuid,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for PluginTerminateEvent {
    fn get_name(&self) -> String {
        String::from("PluginTerminateEvent")
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for PluginTerminateEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array. */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::PluginTerminateEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            target_plugin_name: Some(fbuf.create_string(&self.target_plugin_name)),
            target_plugin_uuid: Some(fbuf.create_string(&self.target_plugin_uuid.hyphenated().to_string())),
        };
        let event_offset = gen_events::PluginTerminateEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::PluginTerminateEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from a vector raw event bytes. */
    fn from_bytes(bytes: Vec<u8>) -> Result<PluginTerminateEvent, Box<dyn Error>>
    where
        Self: Sized {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "PluginTerminateEvent";
        check_event_type(event_type, &event)?;
    
        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_plugin_terminate_event() {
            Some(ev) => ev,
            None =>  return Err(Box::new(Errors::EventCreateFromFlatbuffer(event_type.to_string()))), 
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match PluginTerminateEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => return Result::Ok(ev),
            Err(e) => return Result::Err(Box::new(e)),
        };
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl PluginTerminateEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(target_plugin_uuid: Uuid, target_plugin_name: String) -> Self {
        PluginTerminateEvent {
            created: timestamp_str(),
            target_plugin_name,
            target_plugin_uuid,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. */
    pub fn new_from_gen(ev: gen_events::PluginTerminateEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("created")))},
        };

        // Get the plugin_name.
        let target_plugin_name = match ev.target_plugin_name() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("target_plugin_name")))},
        };

        // Get the uuid.
        let u = match ev.target_plugin_uuid() {
            Some(s) => s,
            None => {return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid")))},
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("target_plugin_uuid"), e.to_string()))},
        };

        // Finally...
        Result::Ok(PluginTerminateEvent {
            created: String::from(created),
            target_plugin_name: String::from(target_plugin_name),
            target_plugin_uuid: uuid,
        })
    }
}

// ***************************************************************************
// PRIVATE FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// bytes_to_gen_event:
// ---------------------------------------------------------------------------
/** Given a reference to a byte array containing the serialized flatbuffer
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
