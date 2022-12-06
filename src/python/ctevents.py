from cProfile import label
import datetime
import uuid
from tokenize import String
import flatbuffers
from gen_events import NewImageEvent, ImageScoredEvent, ImageStoredEvent, ImageDeletedEvent, ImageLabelScore, PluginStartedEvent, PluginTerminateEvent, PluginTerminatingEvent
from gen_events import Event
from gen_events.EventType import EventType

# zmq and socket helper lib
import zmq
from events import get_plugin_socket, get_next_msg, publish_msg, send_quit_command


PYPLUGIN_TCP_PORT = 6000

EVENT_TYPE_BYTE_PREFIX = {
    "NEW_IMAGE": b'\x01\x00',
    "IMAGE_RECEIVED": b'\x02\x00',
    "IMAGE_SCORED": b'\x03\x00',
    "IMAGE_STORED": b'\x04\x00',
    "IMAGE_DELETED": b'\x05\x00',
    "PLUGIN_STARTED": b'\x10\x00',
    "PLUGIN_TERMINATING": b'\x11\x00',
    "PLUGIN_TERMINATE": b'\x12\x00',
}


def _prepend_event_prefix(msg_type, fb_data):
    """
    Add the event prefix bytes, used for zmq message filtering based on subscriptions, to the front of 
    a flatbuffer message.
    """
    try:
        byte_prefix = EVENT_TYPE_BYTE_PREFIX[msg_type]
    except KeyError:
        raise Exception(f"Unrecognized message type {msg_type}")    
    fb_data[0:0] = byte_prefix
    return fb_data


def _remove_event_prefix(data):
    """
    Remove the event prefix bytes, which appear at the beginning of a zmq message and are used for filtering
    the messages delivered to a specific plugin based on the plugin's subscriptions, from the front of a 
    zmq message. The result should be a valid flatbuffers message payload.
    """
    # delete one byte from the beginning of data for each byte in an (arbitrary) event type prefix -- they 
    # will all be the same length.
    for i in range(len(EVENT_TYPE_BYTE_PREFIX['NEW_IMAGE'])):
        del data[0]
    return data

def _generate_new_image_fb_event(uuid: String, format: String, image: bytearray) -> bytearray:
    """
    Create a new image event flatbuffers object
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
    # fb_data = builder.Output() # Of type `bytearray`
    # # still need to prepend the event type bytes prefix
    # fb_data = _prepend_event_prefix("NEW_IMAGE", fb_data)
    # return fb_data


def _generate_new_image_fb_with_prefix(uuid: String, format: String, image: bytearray) -> bytearray:
    """
    Create a new image event message with prefix.
    """
    fb = _generate_new_image_fb_event(uuid, format, image)
    return _prepend_event_prefix("NEW_IMAGE", fb)


def send_new_image_fb_event(socket, uuid: String, format: String, image: bytearray) -> str:
    """
    Send a new image event over the zmq socket.
    Returns a string which is the reply from the event-engine thread or raises an 
    exception on error.
    """
    fb_data = _generate_new_image_fb_event(uuid, format, image)
    # add byte prefix
    data = _prepend_event_prefix(msg_type, fb_data)
    # send the message over the socket
    return publish_msg(socket, data)


# type Score(dict):
#     # list fields and types
#     label: str
#     probability: float
#     image_uuid: uuid.uuid4

def _generate_image_scored_fb_event(image_uuid, scores: "list(dict)"):
    """
    Create a new image scored event flatubuffers object
    """    
    builder = flatbuffers.Builder(1024)
    # ----- create and serialize the individual fields first -----
    # generate a time stamp string formatted  via ISO 8601
    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    uuid_fb = builder.CreateString(image_uuid)

    scores_fb = []
    for score in scores:
        label_fb = builder.CreateString(score['label'])
        uuid_fb = builder.CreateString(str(score['image_uuid']))
        prob_fb = score['probability']
        scores_fb.append({'label': label_fb, 'uuid': uuid_fb, 'prob': prob_fb})
    
    image_label_scores = []
    for score in scores_fb:    
        ImageLabelScore.ImageLabelScoreStart(builder)
        ImageLabelScore.AddImageUuid(builder, score['uuid'])
        ImageLabelScore.AddLabel(builder, score['label'])
        ImageLabelScore.AddProbability(builder, score['prob'])
        image_label_score = ImageLabelScore.ImageLabelScoreEnd(builder)
        image_label_scores.append(image_label_score)
    ImageScoredEvent.ImageScoredEventStartScoresVector(builder, len(image_label_scores))
    for s in reversed(image_label_scores):
        builder.PrependUOffsetTRelative(s)
    scores_fb_vector = builder.EndVector()
    ImageScoredEvent.Start(builder)
    ImageScoredEvent.AddScores(builder, scores_fb_vector)
    ImageScoredEvent.AddEventCreateTs(builder, ts_fb)
    ImageScoredEvent.AddImageUuid(builder, uuid_fb)
    image_scored_event = ImageScoredEvent.End(builder)

    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.ImageScoredEvent)
    Event.AddEvent(builder, image_scored_event)
    root_event = Event.End(builder)

    # call finish to instruct the builder that we are done
    builder.Finish(root_event)
    fb_data = builder.Output() # Of type `bytearray`
    # still need to prepend the event type bytes prefix
    fb_data = _prepend_event_prefix("IMAGE_SCORED", fb_data)
    return fb_data


def _generate_store_image_fb_event(image_uuid: String, destination: String)-> bytearray:
    """
    Create a new event to indicate image has been written to external destination
    """
    builder = flatbuffers.Builder(1024)

    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    image_uuid_fb = builder.CreateString(image_uuid)
    destination_fb = builder.CreateString(destination)

    ImageStoredEvent.Start(builder)
    ImageStoredEvent.AddEventCreateTs(builder, ts_fb)
    ImageStoredEvent.AddImageUuid(builder, image_uuid_fb)
    ImageStoredEvent.AddDestination(builder, destination_fb)
    
    image_stored_event = ImageStoredEvent.End(builder)


    # -- root object --
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.ImageStoredEvent)
    Event.AddEvent(builder, image_stored_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()


def _generate_delete_image_fb_event(image_uuid: String)-> bytearray:
    """
    Create an event that indicates image has been deleted from database
    """
    builder = flatbuffers.Builder(1024)

    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    image_uuid_fb = builder.CreateString(image_uuid)

    ImageDeletedEvent.Start(builder)
    ImageDeletedEvent.AddEventCreateTs(builder, ts_fb)
    ImageDeletedEvent.AddImageUuid(builder, image_uuid_fb)
    
    image_deleted_event = ImageDeletedEvent.End(builder)


    # -- root object --
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.ImageDeletedEvent)
    Event.AddEvent(builder, image_deleted_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()

def _generate_start_plugin_fb_event(plugin_name: String, plugin_uuid: String)-> bytearray:
    """
    Create a plugin started event flatbuffers object
    """
    builder = flatbuffers.Builder(1024)

    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    plugin_name_fb = builder.CreateString(plugin_name)
    plugin_uuid_fb = builder.CreateString(plugin_uuid)

    PluginStartedEvent.Start(builder)
    PluginStartedEvent.AddEventCreateTs(builder, ts_fb)
    PluginStartedEvent.AddPluginUuid(builder, plugin_uuid_fb)
    PluginStartedEvent.AddPluginName(builder, plugin_name_fb)
    
    plugin_started_event = PluginStartedEvent.End(builder)


    # -- root object --
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.PluginStartedEvent)
    Event.AddEvent(builder, plugin_started_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()

def _generate_terminating_plugin_fb_event(plugin_name: String, plugin_uuid: String)-> bytearray:
    """
    Create a plugin terminating event flatbuffers object
    """
    builder = flatbuffers.Builder(1024)

    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    plugin_name_fb = builder.CreateString(plugin_name)
    plugin_uuid_fb = builder.CreateString(plugin_uuid)

    PluginTerminatingEvent.Start(builder)
    PluginTerminatingEvent.AddEventCreateTs(builder, ts_fb)
    PluginTerminatingEvent.AddPluginUuid(builder, plugin_uuid_fb)
    PluginTerminatingEvent.AddPluginName(builder, plugin_name_fb)
    
    plugin_terminating_event = PluginTerminatingEvent.End(builder)


    # -- root object --
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.PluginTerminatingEvent)
    Event.AddEvent(builder, plugin_terminating_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()

def _generate_terminate_plugin_fb_event(target_plugin_name: String, target_plugin_uuid: String)-> bytearray:
    builder = flatbuffers.Builder(1024)

    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    target_plugin_name_fb = builder.CreateString(target_plugin_name)
    target_plugin_uuid_fb = builder.CreateString(target_plugin_uuid)

    PluginTerminateEvent.Start(builder)
    PluginTerminateEvent.AddEventCreateTs(builder, ts_fb)
    PluginTerminateEvent.AddTargetPluginUuid(builder, target_plugin_uuid_fb)
    PluginTerminateEvent.AddTargetPluginName(builder, target_plugin_name_fb)
    
    plugin_terminate_event = PluginTerminateEvent.End(builder)


    # -- root object --
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.PluginTerminateEvent)
    Event.AddEvent(builder, plugin_terminate_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()


def _bytes_to_event(b: bytearray):
    """
    Takes a bytes array, b, (conceptually, this `b` represents a message coming off the zmq socket), and 
    returns the raw Flatbuffers event object associated with it.
    """
    try:
        event = Event.Event.GetRootAs(b, 0)
        return event
    except Exception as e:
        print(f"Got exception from GetRootAs: {e}")
    return None


def _socket_message_to_event(msg: bytearray):
    # first, remove the event type byte prefix
    b = _remove_event_prefix(msg)
    return _bytes_to_event(b)


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
    if event_type_int == EventType.PluginStartedEvent:
        union_plugin_started_event = PluginStartedEvent.PluginStartedEvent()
        union_plugin_started_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_plugin_started_event
    if event_type_int == EventType.PluginTerminatingEvent:
        union_plugin_terminating_event = PluginTerminatingEvent.PluginTerminatingEvent()
        union_plugin_terminating_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_plugin_terminating_event
    if event_type_int == EventType.PluginTerminateEvent:
        union_plugin_terminate_event = PluginTerminateEvent.PluginTerminateEvent()
        union_plugin_terminate_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_plugin_terminate_event
    raise Exception(f"Unrecognized event type {event_type_int}")


def send_new_image_event(socket, uuid: String, format: String, image: bytearray):
    """ 
    Public API for sending a new image event over a ZMQ socket from the component parts.
    """
    # generate the flatbuffer binary blob
    buf = _generate_new_image_fb_event(uuid, format, image)
    # send the message over the socket
    publish_msg(socket, buf)


def test_new_image_event_with_prefix():
    # create some test data --
    uuid_str = str(uuid.uuid4())
    format = 'jpg'
    with open('labrador-pup.jpg', 'rb') as f:
        image = f.read()
        
    # make a test new image event flattbuffer with prefix
    new_image_fb = _generate_new_image_fb_with_prefix(uuid_str, format, image)  
    
    # check that prefix is the right thing
    assert new_image_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['NEW_IMAGE']
    
    # convert the flattbuffer with prefix back to a root event object 
    e = _socket_message_to_event(new_image_fb)

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


def test_new_image_event_fb():
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

def test_image_stored_event_fb():
    # create some test data --
    uuid_str = str(uuid.uuid4())
    destination = "/data"
        
    # make a test new image event flattbuffer
    stored_image_fb = _generate_store_image_fb_event(uuid_str, destination)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(stored_image_fb)

    # convert the root event object to a typed event (of type new image)
    store_image_event = event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert store_image_event.ImageUuid() == uuid_str.encode('utf-8')
    assert store_image_event.Destination() == destination.encode('utf-8')
    
def test_delete_image_event_fb():
    # create some test data --
    uuid_str = str(uuid.uuid4())
        
    # make a test new image event flattbuffer
    delete_image_fb = _generate_delete_image_fb_event(uuid_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(delete_image_fb)

    # convert the root event object to a typed event (of type new image)
    delete_image_event = event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert delete_image_event.ImageUuid() == uuid_str.encode('utf-8')

def test_start_plugin_event_fb():
    # create some test data --
    plugin_name = "plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test new image event flattbuffer
    start_plugin_fb = _generate_start_plugin_fb_event(plugin_name, uuid_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(start_plugin_fb)

    # convert the root event object to a typed event (of type new image)
    start_plugin_event = event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert start_plugin_event.PluginUuid() == uuid_str.encode('utf-8')
    assert start_plugin_event.PluginName() == plugin_name.encode('utf-8')

def test_terminating_plugin_event_fb():
    # create some test data --
    plugin_name = "plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test new image event flattbuffer
    terminating_plugin_fb = _generate_terminating_plugin_fb_event(plugin_name, uuid_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(terminating_plugin_fb)

    # convert the root event object to a typed event (of type new image)
    terminating_plugin_event = event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert terminating_plugin_event.PluginUuid() == uuid_str.encode('utf-8')
    assert terminating_plugin_event.PluginName() == plugin_name.encode('utf-8')

def test_terminate_plugin_event_fb():
        # create some test data --
    target_plugin_name = "target_plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test new image event flattbuffer
    terminate_plugin_fb = _generate_terminate_plugin_fb_event(target_plugin_name, uuid_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(terminate_plugin_fb)

    # convert the root event object to a typed event (of type new image)
    terminate_plugin_event = event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert terminate_plugin_event.TargetPluginUuid() == uuid_str.encode('utf-8')
    assert terminate_plugin_event.TargetPluginName() == target_plugin_name.encode('utf-8')

def test_image_scored_event_fb():
    scores = [
        {"image_uuid": "8f5f3962-d301-4e96-9994-3bd63c472ce8", "label": "lab", "probability": 0.95},
        {"image_uuid": "8f5f3962-d301-4e96-9994-3bd63c472ce8", "label": "golden_retriever", "probability": 0.05},
        {"image_uuid": "8f5f3962-d301-4e96-9994-3bd63c472ce8", "label": "pug", "probability": 0.012}
    ]
    image_uuid = "8f5f3962-d301-4e96-9994-3bd63c472ce8"
    image_scored_fb = _generate_image_scored_fb_event(image_uuid, scores)
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(image_scored_fb)
    # convert the root event object to a typed event (of type new image)
    image_scored_event = event_to_typed_event(e)
    # test that image_scored_event has the same data on it as the original input data...
    assert "8f5f3962-d301-4e96-9994-3bd63c472ce8" == image_scored_event.ImageUuid().decode('utf-8')
    now = datetime.datetime.utcnow().isoformat()
    # assert times have the same year --
    assert now[:4] == image_scored_event.EventCreateTs().decode('utf-8')[:4]
    for i in range(image_scored_event.ScoresLength()):
        # check each field..
        assert image_scored_event.Scores(i).ImageUuid().decode('utf-8') == scores[i]['image_uuid']
        # TODO -- also check label and probability...
        assert image_scored_event.Scores(i).Label().decode('utf-8') == scores[i]['label']
        # print("from fb: " + image_scored_event.Scores(i).Label().decode('utf-8'))
        # print("from py dict: " + scores[i]['label'])
        assert abs(image_scored_event.Scores(i).Probability() - scores[i]['probability']) < 0.1
        # print("from fb: " + str(image_scored_event.Scores(i).Probability()))
        # print("from py dict: " + str(scores[i]['probability']))
    return image_scored_event


def test_send_new_image_event():
    # create the zmq context object
    context = zmq.Context()
    port = 6000
    socket = get_plugin_socket(context, port)
    # TODO -- the following call hangs without a receiver on the other end...
    # reply = send_new_image_event(socket, uuid.uuid4(), format="jpg", image=b'12345abcde')
    print(reply)


if __name__ == "__main__":
    test_new_image_event_fb()
    test_image_scored_event_fb()
    test_image_stored_event_fb()
    test_delete_image_event_fb()
    test_start_plugin_event_fb()
    test_terminating_plugin_event_fb()
    test_terminate_plugin_event_fb()