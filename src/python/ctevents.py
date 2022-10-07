import datetime
import uuid
from tokenize import String
import flatbuffers
from gen_events import NewImageEvent, ImageScoredEvent, ImageStoredEvent, ImageDeletedEvent
from gen_events import Event
from gen_events.EventType import EventType

import zmq

# event engine helper lib
from events import get_plugin_socket, get_next_msg, publish_msg, send_quit_command

PYPLUGIN_TCP_PORT = 6000

def _generate_new_image_fb_event(uuid: String, format: String, image: bytearray) -> bytearray:
    """
    Create a new image event flatubuffers object
    """
    # everything we do will utilize a builder; we can look at whether it would be better to share a singleton
    # builder later.
    builder = flatbuffers.Builder(1024)

    # ----- create and serialize the individual fields first -----
    # generate a time stamp string formatted  via ISO 8601
    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    uuid_fb = builder.CreateString(uuid)
    format_fb = builder.CreateString(format)
    # for vectors, you need to call a "Start" method with the builder and the total length you plan to add
    NewImageEvent.NewImageEventStartImageVector(builder, len(image))
    # add the bytes one at a time and be sure to loop over bytes of image in reverse order so they are added
    # that way; 
    # cf., https://google.github.io/flatbuffers/flatbuffers_guide_tutorial.html, specifically, the comment:
    #     '''
    #     If instead of creating a vector from an existing array you serialize elements individually one by one, 
    #     take care to note that this happens in reverse order, as buffers are built back to front.
    #     '''
    for i in reversed(range(len(image))):
        builder.PrependByte(image[i])
    image_fb = builder.EndVector()

    # ----- start the new image event, add the individual fields, then call End() -----
    # every time you want o create a Table, you need to follow this pattern:
    #    1) Start(builder)
    #    2) AddField1(builder, data)
    #    3) ... add more fields
    #    4) End(builder)
    NewImageEvent.Start(builder)
    NewImageEvent.AddEventCreateTs(builder, ts_fb)
    NewImageEvent.AddImageUuid(builder, uuid_fb)
    NewImageEvent.AddImageFormat(builder, format_fb)
    NewImageEvent.AddImage(builder, image_fb)
    new_image_event = NewImageEvent.End(builder)

    # ----- Create the "root" Event object -----
    # we do this at the very end, as it is "filled" with the specific event bject type, in this case, 
    # the NewImageEvent
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.NewImageEvent)
    Event.AddEvent(builder, new_image_event)
    root_event = Event.End(builder)

    # call finish to instruct the builder that we are done
    builder.Finish(root_event)
    return builder.Output() # Of type `bytearray`


def _bytes_to_event(b: bytearray):
    """
    Takes a bytes array, b, and returns the raw Flatbuffers event object associated with it.
    """
    try:
        event = Event.Event.GetRootAs(b, 0)
        return event
    except Exception as e:
        print(f"Got exception from GetRootAs: {e}")
    return None


def event_to_typed_event(event):
    """
    Takes a raw Event.Event object and returns a specialized typed event (e.g., NewImageEvent, 
    ImageScoredEvent, etc.) by first checking the type.
    """
    event_type_int = event.EventType()
    if event_type_int == EventType.NewImageEvent:
        union_new_image_event = NewImageEvent.NewImageEvent()
        union_new_image_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_new_image_event
    if event_type_int == EventType.ImageScoredEvent:
        union_image_scored_event = ImageScoredEvent.ImageScoredEvent()
        union_image_scored_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_image_scored_event
    if event_type_int == EventType.ImageStoredEvent:
        union_image_stored_event = ImageStoredEvent.ImageStoredEvent()
        union_image_stored_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_image_stored_event
    if event_type_int == EventType.ImageDeletedEvent:
        union_image_deleted_event = ImageDeletedEvent.ImageDeletedEvent()
        union_image_deleted_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_image_deleted_event
    # TODO -- add additional types
    raise Exception(f"Unrecognized event type {event_type_int}")


def send_new_image_event(socket, uuid: String, format: String, image: bytearray):
    """ 
    Public API for sending a new image event over a ZMQ socket from the component parts.
    """
    # generate the flatbuffer binary blob
    buf = _generate_new_image_fb_event(uuid, format, image)
    # send the message over the socket
    publish_msg(socket, buf)


def test():
    """
    A basic test function to check that serializing and deserializing new image event flatbuffers
    works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    format = 'jpg'
    with open('labrador-pup.jpg', 'rb') as f:
        image = f.read()    
    
    # make a test new image event flattbuffer
    new_image_fb = _generate_new_image_fb_event(uuid_str, format, image)

    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(new_image_fb)

    # convert the root event object to a typed event (of type new image)
    new_image_event = event_to_typed_event(e)

    # check the fields; each should match the previous test data we generated
    # format should be the original "jpg", as bytes
    assert new_image_event.ImageFormat() == b'jpg'

    # ImageUuid of flatbuffer should match previous uuid string
    assert new_image_event.ImageUuid() == uuid_str.encode('utf-8')

    # get the image field from the flatbuffer; unfortunately, the flatbuffers API does not give us a simple 
    # wrapper method to do this, so we build a bytearray using the provided Image(i) method, which grabs the 
    # byte at the i^th position.
    image_from_fb = bytearray()
    for i in range(new_image_event.ImageLength()):
        image_from_fb.append(new_image_event.Image(i))
    # the image we built from the flatbuffer should match the original image
    assert image_from_fb == image
    
    # TODO -- incorporate zmq...
    # create the zmq context and socket objects
    # context = zmq.Context()
    # socket = get_plugin_socket(context, PYPLUGIN_TCP_PORT)  
    # send_new_image_event(socket, uuid_str, format, image)


if __name__ == "__main__":
    test()    

    