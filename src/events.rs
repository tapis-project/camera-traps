use event_engine::errors::EngineError;
use event_engine::events::{Event, EventType};
use flatbuffers::{FlatBufferBuilder, InvalidFlatbuffer};
use std::error::Error;
use uuid::Uuid;
use serde::Serialize;

// Logging imports.
use anyhow::Result;

// Application errors.
use crate::config::errors::Errors;
use crate::events_generated::gen_events;
use crate::traps_utils::{timestamp_str, timestamp_str_to_datetime};

// ***************************************************************************
// CONSTANTS
// ***************************************************************************
// Each event is assigned a binary prefix that zqm uses to route incoming
// binary streams to all of the event's subscribers.
pub const NEW_IMAGE_PREFIX: [u8; 2] = [0x01, 0x00];
pub const IMAGE_RECEIVED_PREFIX:      [u8; 2] = [0x02, 0x00];
pub const IMAGE_SCORED_PREFIX:        [u8; 2] = [0x03, 0x00];
pub const IMAGE_STORED_PREFIX:        [u8; 2] = [0x04, 0x00];
pub const IMAGE_DELETED_PREFIX:       [u8; 2] = [0x05, 0x00];
pub const PLUGIN_STARTED_PREFIX:      [u8; 2] = [0x10, 0x00];
pub const PLUGIN_TERMINATING_PREFIX:  [u8; 2] = [0x11, 0x00];
pub const PLUGIN_TERMINATE_PREFIX:    [u8; 2] = [0x12, 0x00];
pub const MONITOR_POWER_START_PREFIX: [u8; 2] = [0x20, 0x00];
pub const MONITOR_POWER_STOP_PREFIX:  [u8; 2] = [0x21, 0x00];
pub const EVENT_PREFIX_LEN: usize = NEW_IMAGE_PREFIX.len();

// ***************************************************************************
// PUBLIC FUNCTIONS
// ***************************************************************************
// ---------------------------------------------------------------------------
// check_event_prefix:
// ---------------------------------------------------------------------------
/** Make sure zqm routing prefix matches the event is supposed to be associated
 * with.  Return true if they match, false otherwise.
 */
pub fn check_event_prefix(prefix: [u8; 2], event_name: &str) -> bool {
    match prefix {
        NEW_IMAGE_PREFIX => {
            event_name == "NewImageEvent" 
        }
        IMAGE_RECEIVED_PREFIX => {
            event_name == "ImageReceivedEvent" 
        }
        IMAGE_SCORED_PREFIX => {
            event_name == "ImageScoredEvent" 
        }
        IMAGE_STORED_PREFIX => {
            event_name == "ImageStoredEvent" 
        }
        IMAGE_DELETED_PREFIX => {
            event_name == "ImageDeletedEvent" 
        }
        PLUGIN_STARTED_PREFIX => {
            event_name == "PluginStartedEvent" 
        }
        PLUGIN_TERMINATING_PREFIX => {
            event_name == "PluginterminatingEvent" 
        }
        PLUGIN_TERMINATE_PREFIX => {
            event_name == "PluginTerminateEvent" 
        }
        MONITOR_POWER_START_PREFIX => {
            event_name == "MonitorPowerStartEvent" 
        }
        MONITOR_POWER_STOP_PREFIX => {
            event_name == "MonitorPowerStopEvent" 
        }
        _ => false,
    }
}

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

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(NEW_IMAGE_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for NewImageEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
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
        Ok(serialize_flatbuffer(NEW_IMAGE_PREFIX, fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<NewImageEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "NewImageEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_new_image_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match NewImageEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("image"))),
        };
        let mut image = Vec::with_capacity(raw.len());
        image.extend_from_slice(raw);

        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("image_uuid"),
                    e.to_string(),
                ))
            }
        };

        // Get the image format string.
        let image_format = match ev.image_format() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("image_format"))),
        };

        // Finally...
        Result::Ok(NewImageEvent {
            created: String::from(created),
            image_uuid: uuid,
            image_format: String::from(image_format),
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
    image_format: String,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageReceivedEvent {
    fn get_name(&self) -> String {
        String::from("ImageReceivedEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(IMAGE_RECEIVED_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageReceivedEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::ImageReceivedEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
            image_format: Some(fbuf.create_string(&self.image_format)),
        };
        let event_offset = gen_events::ImageReceivedEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::ImageReceivedEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(
            IMAGE_RECEIVED_PREFIX,
            fbuf,
            union_args,
        ))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageReceivedEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageReceivedEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_received_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageReceivedEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
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
    pub fn new(image_uuid: Uuid, image_format: String) -> Self {
        ImageReceivedEvent {
            created: timestamp_str(),
            image_uuid,
            image_format,
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("image_uuid"),
                    e.to_string(),
                ))
            }
        };

        // Get the image format.
        let image_format = match ev.image_format() {
            Some(f) => f,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("image_format"))),
        };

        // Finally...
        Result::Ok(ImageReceivedEvent {
            created: String::from(created),
            image_uuid: uuid,
            image_format: String::from(image_format),
        })
    }
}

// ===========================================================================
// ImageScoredEvent:
// ===========================================================================
// ------------------------------
// ------ ImageLabelScore
// ------------------------------
#[derive(Serialize)]
pub struct ImageLabelScore {
    label: String,
    probability: f32,
}

impl ImageLabelScore {
    #![allow(unused)]
    pub fn new(image_uuid: Uuid, label: String, probability: f32) -> Self {
        ImageLabelScore {
            label,
            probability,
        }
    }

    pub fn new_from_gen(ev: gen_events::ImageLabelScore) -> Result<Self, Errors> {
        // Get the image label string.
        let label = match ev.label() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("label"))),
        };

        // Get the label's probability value.
        let probability = ev.probability();

        // Return the object.
        Result::Ok(ImageLabelScore {
            label: String::from(label),
            probability,
        })
    }
}

// ------------------------------
// ------ ImageScoredEvent
// ------------------------------
#[derive(Serialize)]
pub struct ImageScoredEvent {
    created: String,
    image_uuid: Uuid,
    image_format: String, 
    scores: Vec<ImageLabelScore>,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageScoredEvent {
    fn get_name(&self) -> String {
        String::from("ImageScoredEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(IMAGE_SCORED_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageScoredEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Create a vector of gen_events::ImageLabelScores from this object's scores.
        // First create a vector to hold the gen_events::ImageLabelScore objects.
        let mut image_label_scores =
            Vec::<flatbuffers::WIPOffset<gen_events::ImageLabelScore>>::new();
        for score in &self.scores {
            // Assign the string fields.
            let label = Some(fbuf.create_string(&score.label));

            // Create each generated score object
            let im_score = gen_events::ImageLabelScore::create(
                &mut fbuf,
                &gen_events::ImageLabelScoreArgs {
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
            image_format: Some(fbuf.create_string(&self.image_format)),
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
        Ok(serialize_flatbuffer(IMAGE_SCORED_PREFIX, fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageScoredEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageScoredEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_scored_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageScoredEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl ImageScoredEvent {
    // ----------------------------------------------------------------------
    // accessors:
    // ----------------------------------------------------------------------
    pub fn get_created(&self) -> &String {
        &self.created
    }
    pub fn get_image_uuid(&self) -> &Uuid {
        &self.image_uuid
    }
    pub fn get_image_format(&self) -> &String {
        &self.image_format
    }
    pub fn get_scores(&self) -> &Vec<ImageLabelScore> {
        &self.scores
    }

    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #[allow(unused)]
    pub fn new(image_uuid: Uuid, image_format: String, scores: Vec<ImageLabelScore>) -> Self {
        ImageScoredEvent {
            created: timestamp_str(),
            image_uuid,
            image_format,
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("image_uuid"),
                    e.to_string(),
                ))
            }
        };

        // Get the image format string.
        let image_format = match ev.image_format() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("image_format"))),
        };

        // Get the list of scores.
        let gen_scores = match ev.scores() {
            Some(v) => v,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("scores"))),
        };

        // Iterate through each generated score and add to list of event scores.
        let mut scores: Vec<ImageLabelScore> = Vec::new();
        for gen_score in gen_scores {
            // Extract the label.
            let label = match gen_score.label() {
                Some(s) => s,
                None => {
                    return Result::Err(Errors::EventReadFlatbuffer(String::from(
                        "ImageLabelScore.label",
                    )))
                }
            };

            // Extract the probability.
            let probability = gen_score.probability();

            // Create the event imagelabelscore and add it to the vector.
            let new_score = ImageLabelScore {
                label: label.to_string(),
                probability,
            };
            scores.push(new_score);
        }

        // Finally...
        Result::Ok(ImageScoredEvent {
            created: String::from(created),
            image_uuid: uuid,
            image_format: String::from(image_format),
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
    image_format: String,
    destination: String,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageStoredEvent {
    fn get_name(&self) -> String {
        String::from("ImageStoredEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(IMAGE_STORED_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageStoredEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::ImageStoredEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
            image_format: Some(fbuf.create_string(&self.image_format)),
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
        Ok(serialize_flatbuffer(IMAGE_STORED_PREFIX, fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageStoredEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageStoredEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_stored_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageStoredEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
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
    pub fn new(image_uuid: Uuid, image_format: String, destination: String) -> Self {
        ImageStoredEvent {
            created: timestamp_str(),
            image_uuid,
            image_format,
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("image_uuid"),
                    e.to_string(),
                ))
            }
        };

        // Get the image format string.
        let image_format = match ev.image_format() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("image_format"))),
        };

        // Get the destination.
        let destination = match ev.destination() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("destination"))),
        };

        // Finally...
        Result::Ok(ImageStoredEvent {
            created: String::from(created),
            image_uuid: uuid,
            image_format: String::from(image_format),
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
    image_format: String,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for ImageDeletedEvent {
    fn get_name(&self) -> String {
        String::from("ImageDeletedEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(IMAGE_DELETED_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for ImageDeletedEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::ImageDeletedEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            image_uuid: Some(fbuf.create_string(&self.image_uuid.hyphenated().to_string())),
            image_format: Some(fbuf.create_string(&self.image_format)),
        };
        let event_offset = gen_events::ImageDeletedEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::ImageDeletedEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(IMAGE_DELETED_PREFIX, fbuf, union_args))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<ImageDeletedEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "ImageDeletedEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_image_deleted_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match ImageDeletedEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
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
    pub fn new(image_uuid: Uuid, image_format: String) -> Self {
        ImageDeletedEvent {
            created: timestamp_str(),
            image_uuid,
            image_format,
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the uuid.
        let u = match ev.image_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("image_uuid"),
                    e.to_string(),
                ))
            }
        };

        // Get the image format string.
        let image_format = match ev.image_format() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("image_format"))),
        };

        // Finally...
        Result::Ok(ImageDeletedEvent {
            created: String::from(created),
            image_uuid: uuid,
            image_format: String::from(image_format),
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

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(PLUGIN_STARTED_PREFIX.to_vec())
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
        Ok(serialize_flatbuffer(
            PLUGIN_STARTED_PREFIX,
            fbuf,
            union_args,
        ))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<PluginStartedEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "PluginStartedEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_plugin_started_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match PluginStartedEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the plugin_name.
        let plugin_name = match ev.plugin_name() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("plugin_name"))),
        };

        // Get the uuid.
        let u = match ev.plugin_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("plugin_uuid"),
                    e.to_string(),
                ))
            }
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

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(PLUGIN_TERMINATING_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for PluginTerminatingEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
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
        Ok(serialize_flatbuffer(
            PLUGIN_TERMINATING_PREFIX,
            fbuf,
            union_args,
        ))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<PluginTerminatingEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "PluginTerminatingEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_plugin_terminating_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match PluginTerminatingEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the plugin_name.
        let plugin_name = match ev.plugin_name() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("plugin_name"))),
        };

        // Get the uuid.
        let u = match ev.plugin_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("plugin_uuid"),
                    e.to_string(),
                ))
            }
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

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(PLUGIN_TERMINATE_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for PluginTerminateEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::PluginTerminateEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            target_plugin_name: Some(fbuf.create_string(&self.target_plugin_name)),
            target_plugin_uuid: Some(
                fbuf.create_string(&self.target_plugin_uuid.hyphenated().to_string()),
            ),
        };
        let event_offset = gen_events::PluginTerminateEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::PluginTerminateEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(
            PLUGIN_TERMINATE_PREFIX,
            fbuf,
            union_args,
        ))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a NewImageEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<PluginTerminateEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "PluginTerminateEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_plugin_terminate_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match PluginTerminateEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
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
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get the plugin_name.
        let target_plugin_name = match ev.target_plugin_name() {
            Some(s) => s,
            None => {
                return Result::Err(Errors::EventReadFlatbuffer(String::from(
                    "target_plugin_name",
                )))
            }
        };

        // Get the uuid.
        let u = match ev.target_plugin_uuid() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("uuid"))),
        };
        let uuid = match Uuid::parse_str(u) {
            Ok(u) => u,
            Err(e) => {
                return Result::Err(Errors::UUIDParseError(
                    String::from("target_plugin_uuid"),
                    e.to_string(),
                ))
            }
        };

        // Finally...
        Result::Ok(PluginTerminateEvent {
            created: String::from(created),
            target_plugin_name: String::from(target_plugin_name),
            target_plugin_uuid: uuid,
        })
    }
}

// ===========================================================================
// MonitorPowerStartEvent:
// ===========================================================================
// All possible poew monitoring options.
#[allow(clippy::upper_case_acronyms)]
pub enum  MonitorType { ALL = 1, CPU, GPU, DRAM, }

pub struct MonitorPowerStartEvent {
    created: String,
    pids: Vec<i32>,
    monitor_types: Vec<MonitorType>,
    monitor_start: String,
    monitor_seconds: u32,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for MonitorPowerStartEvent {
    fn get_name(&self) -> String {
        String::from("MonitorPowerStartEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(MONITOR_POWER_START_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for MonitorPowerStartEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Populate a list of gen_events monitor types.
        let mut gen_types: Vec<gen_events::MonitorType> = Vec::new();
        for mtype in &self.monitor_types {
            match *mtype {
                MonitorType::ALL  => gen_types.push(gen_events::MonitorType::ALL),
                MonitorType::CPU  => gen_types.push(gen_events::MonitorType::CPU),
                MonitorType::GPU  => gen_types.push(gen_events::MonitorType::GPU),
                MonitorType::DRAM => gen_types.push(gen_events::MonitorType::DRAM),
            }
        }

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::MonitorPowerStartEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            pids: Some(fbuf.create_vector(&self.pids)),
            monitor_types: Some(fbuf.create_vector(&gen_types)),
            monitor_start_ts: Some(fbuf.create_string(&self.monitor_start)),
            monitor_seconds: self.monitor_seconds,
         };
        let event_offset = gen_events::MonitorPowerStartEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::MonitorPowerStartEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(
            MONITOR_POWER_START_PREFIX,
            fbuf,
            union_args,
        ))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a MonitorPowerStartEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<MonitorPowerStartEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "MonitorPowerStartEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_monitor_power_start_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match MonitorPowerStartEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl MonitorPowerStartEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(pids: Vec<i32>, monitor_types: Vec<MonitorType>, 
                monitor_start: String, monitor_seconds: u32) -> Self {
        MonitorPowerStartEvent {
            created: timestamp_str(),
            pids, 
            monitor_types,
            monitor_start,
            monitor_seconds,
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. 
     * This function enforces the constraints that the pids and monitor_types
     * lists must contain at least one element each.
    */
    pub fn new_from_gen(ev: gen_events::MonitorPowerStartEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get pids array.
        let gen_pids = match ev.pids() {
            Some(v) => v,
            None => {
                return Result::Err(Errors::EventReadFlatbuffer(String::from("pids")))
            }
        };
        // Validate there's something to do.
        if gen_pids.is_empty() {
            return Result::Err(Errors::EventReceivedEmptyList(
                "MonitorPowerStartEvent".to_string(), "pids".to_string()))
        }
        // Extract the pids into a standard vector.
        let mut pids: Vec<i32> = Vec::new(); 
        for pid in gen_pids {
            pids.push(pid);
        }

        // Get monitor types array.
        let gen_monitor_types = match ev.monitor_types() {
            Some(v) => v,
            None => {
                return Result::Err(Errors::EventReadFlatbuffer(String::from("montitor_types")))
            }
        };
        // Validate there's something to do.
        if gen_monitor_types.is_empty() {
            return Result::Err(Errors::EventReceivedEmptyList(
                "MonitorPowerStartEvent".to_string(), "monitor_types".to_string()))
        }
        
        // Extract the monitor types into a standard vector.
        let mut monitor_types: Vec<MonitorType> = Vec::new();
        for gen_type in gen_monitor_types {
            let gen_type_str = match gen_type.variant_name() {
                Some(s) => s,
                None => {
                    return Result::Err(Errors::EventReadFlatbuffer(String::from("montitor_type")))
                }
            };
            // Update this list whenever the there's a change to monitor types.
            match gen_type_str {
                "ALL"  => monitor_types.push(MonitorType::ALL),
                "CPU"  => monitor_types.push(MonitorType::CPU),
                "GPU"  => monitor_types.push(MonitorType::GPU),
                "DRAM" => monitor_types.push(MonitorType::DRAM),
                _ => {
                    return Result::Err(Errors::EventReadFlatbuffer(
                        "montitor_type".to_string() + " Unknown -> " + gen_type_str))
                }
            };
        }

        // Get the monitor start timestamp.  It should always be a valid
        // UTC datetime, but it has no effec if it's in the past.
        let monitor_start = match ev.monitor_start_ts() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("monitor_start"))),
        };
        // Validate that we have a well-formed datetime or the empty string.
        // The empty string means monitoring should start immediately.
        if !monitor_start.is_empty() {
            let dt = match timestamp_str_to_datetime(monitor_start) {
                Ok(d) => d,
                Err(e) => {
                    return Result::Err(Errors::DateParseError(monitor_start.to_string(), e.to_string()))
                },
            };
        }

        // Get the monitoring duration in seconds.
        let monitor_seconds = ev.monitor_seconds();

        // Finally...
        Result::Ok(MonitorPowerStartEvent {
            created: String::from(created),
            pids,
            monitor_types,
            monitor_start: monitor_start.to_string(),
            monitor_seconds,
        })
    }
}

// ===========================================================================
// MonitorPowerStopEvent:
// ===========================================================================
pub struct MonitorPowerStopEvent {
    created: String,
    pids: Vec<i32>,
}

// ------------------------------
// ------ Trait EventType
// ------------------------------
impl EventType for MonitorPowerStopEvent {
    fn get_name(&self) -> String {
        String::from("MonitorPowerStopEvent")
    }

    fn get_filter(&self) -> Result<Vec<u8>, EngineError> {
        Result::Ok(MONITOR_POWER_STOP_PREFIX.to_vec())
    }
}

// ------------------------------
// ------ Trait Event
// ------------------------------
impl Event for MonitorPowerStopEvent {
    // ----------------------------------------------------------------------
    // to_bytes:
    // ----------------------------------------------------------------------
    /** Convert the event to a raw byte array (prefix + flatbuffer). */
    fn to_bytes(&self) -> Result<Vec<u8>, EngineError> {
        // Create a new flatbuffer.
        let mut fbuf = FlatBufferBuilder::new();

        // Assign the generated arguments object from our application object.
        // Create the generated event offset object using the generated arguments.
        let args = gen_events::MonitorPowerStopEventArgs {
            event_create_ts: Some(fbuf.create_string(&self.created)),
            pids: Some(fbuf.create_vector(&self.pids)),
         };
        let event_offset = gen_events::MonitorPowerStopEvent::create(&mut fbuf, &args);

        // Create generated event arguments which are a union for all possible events.
        // Create the generated event union offset object using the union arguments.
        let union_args = gen_events::EventArgs {
            event_type: gen_events::EventType::MonitorPowerStopEvent,
            event: Some(event_offset.as_union_value()),
        };

        // All event serializations are completed in the same way.
        Ok(serialize_flatbuffer(
            MONITOR_POWER_STOP_PREFIX,
            fbuf,
            union_args,
        ))
    }

    // ----------------------------------------------------------------------
    // from_bytes:
    // ----------------------------------------------------------------------
    /** Get a MonitorPowerStopEvent from raw event bytes that do NOT include the zqm prefix. */
    fn from_bytes(bytes: Vec<u8>) -> Result<MonitorPowerStopEvent, Box<dyn Error>>
    where
        Self: Sized,
    {
        // Get the union of all possible generated events.
        let event = bytes_to_gen_event(&bytes)?;

        // Validate that we recieved the expected type of event.
        let event_type = "MonitorPowerStopEvent";
        check_event_type(event_type, &event)?;

        // Create the generated event from the raw flatbuffer.
        let flatbuf_event = match event.event_as_monitor_power_stop_event() {
            Some(ev) => ev,
            None => {
                return Err(Box::new(Errors::EventCreateFromFlatbuffer(
                    event_type.to_string(),
                )))
            }
        };

        // Return a camera-trap event given the flatbuffer generated event.
        match MonitorPowerStopEvent::new_from_gen(flatbuf_event) {
            Ok(ev) => Result::Ok(ev),
            Err(e) => Result::Err(Box::new(e)),
        }
    }
}

// ------------------------------
// ------ Associated Functions
// ------------------------------
impl MonitorPowerStopEvent {
    // ----------------------------------------------------------------------
    // new:
    // ----------------------------------------------------------------------
    #![allow(unused)]
    pub fn new(pids: Vec<i32>) -> Self {
        MonitorPowerStopEvent {
            created: timestamp_str(),
            pids, 
        }
    }

    // ----------------------------------------------------------------------
    // new_from_gen:
    // ----------------------------------------------------------------------
    /** Construct a new event object from a generated flatbuffer object. 
     * This function enforces the constraints that the pids list must contain
     * at least one element.
    */
    pub fn new_from_gen(ev: gen_events::MonitorPowerStopEvent) -> Result<Self, Errors> {
        // Get the timestamp.
        let created = match ev.event_create_ts() {
            Some(s) => s,
            None => return Result::Err(Errors::EventReadFlatbuffer(String::from("created"))),
        };

        // Get pids array.
        let gen_pids = match ev.pids() {
            Some(v) => v,
            None => {
                return Result::Err(Errors::EventReadFlatbuffer(String::from("pids")))
            }
        };
        // Validate there's something to do.
        if gen_pids.is_empty() {
            return Result::Err(Errors::EventReceivedEmptyList(
                "MonitorPowerStopEvent".to_string(), "pids".to_string()))
        }
        // Extract the pids into a standard vector.
        let mut pids: Vec<i32> = Vec::new(); 
        for pid in gen_pids {
            pids.push(pid);
        }

        // Finally...
        Result::Ok(MonitorPowerStopEvent {
            created: String::from(created),
            pids,
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
    Result::Ok(gen_events::root_as_event(msg_bytes)?)
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
        None => {
            return Err(Errors::EventReadTypeError(expected.to_string()));
        }
    };

    // Check that we got the expected event type.
    if expected != event_type {
        return Err(Errors::EventUnexpectedError(
            expected.to_string(),
            event_type.to_string(),
        ));
    };

    // Success.
    Ok(())
}

// ---------------------------------------------------------------------------
// serialize_flatbuffer:
// ---------------------------------------------------------------------------
fn serialize_flatbuffer(
    prefix: [u8; 2],
    mut fbuf: FlatBufferBuilder,
    union_args: gen_events::EventArgs,
) -> Vec<u8> {
    // Get the offset of the particular event already encoded in the union argument.
    let union_offset = gen_events::Event::create(&mut fbuf, &union_args);

    // Complete the flatbuffer and extract its data as a byte array.
    fbuf.finish(union_offset, None);
    let bytes = fbuf.finished_data();

    // Copy the raw data into a properly sized vector.
    let mut byte_vec: Vec<u8> = Vec::with_capacity(bytes.len() + prefix.len());
    byte_vec.extend_from_slice(&prefix);
    byte_vec.extend_from_slice(bytes);
    byte_vec
}

// ***************************************************************************
// TESTS
// ***************************************************************************
#[cfg(test)]
mod tests {
    use event_engine::events::Event;

    use super::{ImageLabelScore, ImageScoredEvent, EVENT_PREFIX_LEN};

    #[test]
    fn here_i_am() {
        println!("file test: events.rs");
    }

    #[test]
    fn test_image_scored_event() {
        let image_uuid_1 = uuid::Uuid::new_v4();
        let image_uuid_2 = uuid::Uuid::new_v4();
        let image_uuid_3 = uuid::Uuid::new_v4();
        let prob_1: f32 = 0.85;
        let prob_2: f32 = 0.125;
        let prob_3: f32 = 0.025;
        let scores = vec![
            ImageLabelScore::new(image_uuid_1, "test1".to_string(), prob_1),
            ImageLabelScore::new(image_uuid_2, "test2".to_string(), prob_2),
            ImageLabelScore::new(image_uuid_3, "test3".to_string(), prob_3),
        ];
        let image_scored_event = ImageScoredEvent::new(image_uuid_1, "png".to_string(), scores);
        let image_scored_event_bytes = image_scored_event.to_bytes().unwrap();
        let fbuf_bytes = &image_scored_event_bytes[EVENT_PREFIX_LEN..];
        let image_scored_event_deser =
            ImageScoredEvent::from_bytes(fbuf_bytes.to_vec()).unwrap();
        // println!("image scored event deser: {:?}", image_scored_event_deser);
        // check that the serialization and deserialization produced the original
        assert_eq!(image_scored_event_deser.scores[0].probability, prob_1);
        assert_eq!(image_scored_event_deser.scores[1].probability, prob_2);
        assert_eq!(image_scored_event_deser.scores[2].probability, prob_3);
        for s in image_scored_event_deser.scores {
            println!("deserialized score probability: {:?}", s.probability);
        }
    }
}
