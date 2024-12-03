from cProfile import label
import datetime
import uuid
from tokenize import String
import flatbuffers
from ctevents.gen_events import NewImageEvent, ImageReceivedEvent, ImageScoredEvent, ImageStoredEvent, ImageDeletedEvent, ImageLabelScore, PluginStartedEvent, PluginTerminateEvent, PluginTerminatingEvent, MonitorPowerStartEvent, MonitorPowerStopEvent, MonitorType
from ctevents.gen_events import Event
from ctevents.gen_events.EventType import EventType

# zmq and socket helper lib
import zmq
from pyevents.events import publish_msg

PYPLUGIN_TCP_PORT = 6000

# pub const NEW_IMAGE_PREFIX: [u8; 2] = [0x01, 0x00];
# pub const IMAGE_RECEIVED_PREFIX:      [u8; 2] = [0x02, 0x00];
# pub const IMAGE_SCORED_PREFIX:        [u8; 2] = [0x03, 0x00];
# pub const IMAGE_STORED_PREFIX:        [u8; 2] = [0x04, 0x00];
# pub const IMAGE_DELETED_PREFIX:       [u8; 2] = [0x05, 0x00];
# pub const PLUGIN_STARTED_PREFIX:      [u8; 2] = [0x10, 0x00];
# pub const PLUGIN_TERMINATING_PREFIX:  [u8; 2] = [0x11, 0x00];
# pub const PLUGIN_TERMINATE_PREFIX:    [u8; 2] = [0x12, 0x00];
# pub const MONITOR_POWER_START_PREFIX: [u8; 2] = [0x20, 0x00];
# pub const MONITOR_POWER_STOP_PREFIX:  [u8; 2] = [0x21, 0x00];

EVENT_TYPE_BYTE_PREFIX = {
    "NEW_IMAGE": b'\x01\x00',
    "IMAGE_RECEIVED": b'\x02\x00',
    "IMAGE_SCORED": b'\x03\x00',
    "IMAGE_STORED": b'\x04\x00',
    "IMAGE_DELETED": b'\x05\x00',
    "PLUGIN_STARTED": b'\x10\x00',
    "PLUGIN_TERMINATING": b'\x11\x00',
    "PLUGIN_TERMINATE": b'\x12\x00',
    "MONITOR_POWER_START": b'\x20\x00',
    "MONITOR_POWER_STOP": b'\x21\x00'
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
    data = _generate_new_image_fb_with_prefix(uuid, format, image)
    # send the message over the socket
    return publish_msg(socket, data)

def _generate_image_received_fb_event(image_uuid: String, image_format: String) -> bytearray:
    builder = flatbuffers.Builder(1024)
    
    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    uuid_fb = builder.CreateString(image_uuid)
    format_fb = builder.CreateString(image_format)

    ImageReceivedEvent.Start(builder)
    ImageReceivedEvent.AddEventCreateTs(builder, ts_fb)
    ImageReceivedEvent.AddImageUuid(builder, uuid_fb)
    ImageReceivedEvent.AddImageFormat(builder, format_fb)

    image_received_event = ImageReceivedEvent.End(builder)

    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.ImageReceivedEvent)
    Event.AddEvent(builder,image_received_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()

def _generate_image_received_fb_with_prefix(image_uuid, image_format):
    """
    Create an image received event message with prefix.
    """
    fb = _generate_image_received_fb_event(image_uuid, image_format)
    return _prepend_event_prefix("IMAGE_RECEIVED", fb)

def _generate_image_scored_fb_event(image_uuid, image_format, scores: "list(dict)"):
    """
    Create a new image scored event flatubuffers object
    """    
    builder = flatbuffers.Builder(1024)
    # ----- create and serialize the individual fields first -----
    # generate a time stamp string formatted  via ISO 8601
    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    uuid_fb = builder.CreateString(image_uuid)
    format_fb = builder.CreateString(image_format)

    scores_fb = []
    for score in scores:
        label_fb = builder.CreateString(score['label'])
        prob_fb = score['probability']
        scores_fb.append({'label': label_fb, 'prob': prob_fb})
    
    image_label_scores = []
    for score in scores_fb:    
        ImageLabelScore.ImageLabelScoreStart(builder)
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
    ImageScoredEvent.AddImageFormat(builder, format_fb)
    image_scored_event = ImageScoredEvent.End(builder)

    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.ImageScoredEvent)
    Event.AddEvent(builder, image_scored_event)
    root_event = Event.End(builder)

    # call finish to instruct the builder that we are done
    builder.Finish(root_event)
    return builder.Output() # Of type `bytearray`

def _generate_image_scored_fb_with_prefix(image_uuid, image_format, scores: "list(dict)") -> bytearray:
    """
    Create an image scored event message with prefix.
    """
    fb = _generate_image_scored_fb_event(image_uuid, image_format, scores)
    return _prepend_event_prefix("IMAGE_SCORED", fb)

def send_image_scored_fb_event(socket, image_uuid, image_format, scores: "list(dict)") -> str:
    """
    Send an image scored event over the zmq socket.
    Returns a string which is the reply from the event-engine thread or raises an 
    exception on error.
    """
    fb_data = _generate_image_scored_fb_with_prefix(image_uuid, image_format, scores)
    return publish_msg(socket, fb_data)

def _generate_store_image_fb_event(image_uuid: String, image_format: String, destination: String)-> bytearray:
    """
    Create a new event to indicate image has been written to external destination
    """
    builder = flatbuffers.Builder(1024)

    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    image_uuid_fb = builder.CreateString(image_uuid)
    destination_fb = builder.CreateString(destination)
    image_format_fb = builder.CreateString(image_format)

    ImageStoredEvent.Start(builder)
    ImageStoredEvent.AddEventCreateTs(builder, ts_fb)
    ImageStoredEvent.AddImageUuid(builder, image_uuid_fb)
    ImageStoredEvent.AddDestination(builder, destination_fb)
    ImageStoredEvent.AddImageFormat(builder, image_format_fb)
    
    image_stored_event = ImageStoredEvent.End(builder)

    # -- root object --
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.ImageStoredEvent)
    Event.AddEvent(builder, image_stored_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()

def _generate_store_image_fb_with_prefix(image_uuid: String, image_format: String, destination: String) -> bytearray:
    """
    Create a store image event message with prefix.
    """
    fb = _generate_store_image_fb_event(image_uuid, image_format, destination)
    return _prepend_event_prefix("IMAGE_STORED", fb)

def send_store_image_fb_event(socket, image_uuid, destination) -> str:
    """
    Send a store image event over the zmq socket.
    Returns a string which is the reply from the event-engine thread or raises an 
    exception on error.
    """
    fb_data = _generate_store_image_fb_with_prefix(image_uuid, destination)
    return publish_msg(socket, fb_data)

def _generate_delete_image_fb_event(image_uuid: String, image_format: String)-> bytearray:
    """
    Create an event that indicates image has been deleted from database
    """
    builder = flatbuffers.Builder(1024)

    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    image_uuid_fb = builder.CreateString(image_uuid)
    image_format_fb = builder.CreateString(image_format)

    ImageDeletedEvent.Start(builder)
    ImageDeletedEvent.AddEventCreateTs(builder, ts_fb)
    ImageDeletedEvent.AddImageUuid(builder, image_uuid_fb)
    ImageDeletedEvent.AddImageFormat(builder, image_format_fb)

    image_deleted_event = ImageDeletedEvent.End(builder)

    # -- root object --
    Event.Start(builder)
    Event.EventAddEventType(builder, EventType.ImageDeletedEvent)
    Event.AddEvent(builder, image_deleted_event)
    root_event = Event.End(builder)

    builder.Finish(root_event)
    return builder.Output()

def _generate_delete_image_fb_with_prefix(image_uuid: String, image_format: String) -> bytearray:
    """
    Create a delete image event message with prefix.
    """
    fb = _generate_delete_image_fb_event(image_uuid, image_format)
    return _prepend_event_prefix("IMAGE_DELETED", fb)

def send_delete_image_fb_event(socket, image_uuid) -> str:
    """
    Send a delete image event over the zmq socket.
    Returns a string which is the reply from the event-engine thread or raises an 
    exception on error.
    """
    fb_data = _generate_delete_image_fb_with_prefix(image_uuid)
    return publish_msg(socket, fb_data)

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

def _generate_start_plugin_fb_with_prefix(plugin_name: String, plugin_uuid: String) -> bytearray:
    """
    Create a start plugin event message with prefix.
    """
    fb = _generate_start_plugin_fb_event(plugin_name, plugin_uuid)
    return _prepend_event_prefix("PLUGIN_STARTED", fb)

def send_start_plugin_fb_event(socket, plugin_name, plugin_uuid) -> str:
    """
    Send a start plugin event over the zmq socket.
    Returns a string which is the reply from the event-engine thread or raises an 
    exception on error.
    """
    fb_data = _generate_store_image_fb_with_prefix(plugin_name, plugin_uuid)
    return publish_msg(socket, fb_data)

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

def _generate_terminating_plugin_fb_with_prefix(plugin_name: String, plugin_uuid: String) -> bytearray:
    """
    Create a terminating plugin event message with prefix.
    """
    fb = _generate_terminating_plugin_fb_event(plugin_name, plugin_uuid)
    return _prepend_event_prefix("PLUGIN_TERMINATING", fb)

def send_terminating_plugin_fb_event(socket, plugin_name, plugin_uuid) -> str:
    """
    Send a terminating plugin event over the zmq socket.
    Returns a string which is the reply from the event-engine thread or raises an 
    exception on error.
    """
    fb_data = _generate_terminating_plugin_fb_with_prefix(plugin_name, plugin_uuid)
    return publish_msg(socket, fb_data)

def _generate_terminate_plugin_fb_event(target_plugin_name: String, target_plugin_uuid: String)-> bytearray:
    """
    Create a terminate plugin flatbuffers object event
    """
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

def _generate_terminate_plugin_fb_with_prefix(target_plugin_name: String, target_plugin_uuid: String) -> bytearray:
    """
    Create a terminate plugin event message with prefix.
    """
    fb = _generate_terminate_plugin_fb_event(target_plugin_name, target_plugin_uuid)
    return _prepend_event_prefix("PLUGIN_TERMINATE", fb)

def send_terminate_plugin_fb_event(socket, target_plugin_name, target_plugin_uuid) -> str:
    """
    Send a terminating plugin event over the zmq socket.
    Returns a string which is the reply from the event-engine thread or raises an 
    exception on error.
    """
    fb_data = _generate_terminate_plugin_fb_with_prefix(target_plugin_name, target_plugin_uuid)
    return publish_msg(socket, fb_data)


def _generate_monitor_power_start_event(pids: list, monitor_types: list, monitor_seconds: int) -> bytearray:
    """
    Create a monitor power start event message
    """
    builder = flatbuffers.Builder(1024)
    
    # generate a time stamp string formatted  via ISO 8601
    ts = datetime.datetime.utcnow().isoformat()
    ts_fb = builder.CreateString(ts)
    
    # generate monitor start time stamp
    monitor_start_ts = datetime.datetime.utcnow().isoformat()
    monitor_start_ts_fb = builder.CreateString(monitor_start_ts)
    
    # Start adding Pids
    MonitorPowerStartEvent.MonitorPowerStartEventStartPidsVector(builder, len(pids))
    for pid in reversed(pids): 
        builder.PrependInt32(pid)
    pids_fb = builder.EndVector()
    
    # Start adding MonitorTypes
    MonitorPowerStartEvent.MonitorPowerStartEventStartMonitorTypesVector(builder, len(monitor_types))
    for monitor_type in reversed(monitor_types): 
        builder.PrependInt8(monitor_type)
    monitor_types_fb = builder.EndVector()
    
    # Start building the MonitorPowerStartEvent
    MonitorPowerStartEvent.MonitorPowerStartEventStart(builder)
    MonitorPowerStartEvent.MonitorPowerStartEventAddEventCreateTs(builder, ts_fb)
    MonitorPowerStartEvent.MonitorPowerStartEventAddPids(builder, pids_fb)
    MonitorPowerStartEvent.MonitorPowerStartEventAddMonitorTypes(builder, monitor_types_fb)
    MonitorPowerStartEvent.MonitorPowerStartEventAddMonitorStartTs(builder, monitor_start_ts_fb)
    MonitorPowerStartEvent.MonitorPowerStartEventAddMonitorSeconds(builder, monitor_seconds)
    monitor_power_start_event = MonitorPowerStartEvent.MonitorPowerStartEventEnd(builder)
    
    # Start building the generic Event
    Event.EventStart(builder)
    Event.EventAddEventType(builder, EventType.MonitorPowerStartEvent)
    Event.EventAddEvent(builder, monitor_power_start_event)
    root_event = Event.EventEnd(builder)

    builder.Finish(root_event)
    return builder.Output()

def _generate_monitor_power_start_event_with_prefix(pids: list, monitor_types: list, monitor_seconds: int) -> bytearray:
    """
    Create a monitor power start event message with prefix
    """
    fb = _generate_monitor_power_start_event(pids, monitor_types, monitor_seconds)
    return _prepend_event_prefix("MONITOR_POWER_START", fb)

def send_monitor_power_start_fb_event(socket, pids: list, monitor_types: list, monitor_seconds: int) -> str:
    """
    Send a monitor power event over the zmq socket
    TODO: need way to handle multiple pids in future
    """
    fb_data = _generate_monitor_power_start_event_with_prefix(pids, monitor_types, monitor_seconds)
    a = publish_msg(socket, fb_data)
    return a

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


def _event_to_typed_event(event):
    """
    Takes a raw Event.Event object and returns a specialized typed event (e.g., NewImageEvent, 
    ImageScoredEvent, etc.) by first checking the type.
    """
    event_type_int = event.EventType()
    if event_type_int == EventType.NewImageEvent:
        union_new_image_event = NewImageEvent.NewImageEvent()
        union_new_image_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_new_image_event
    if event_type_int == EventType.ImageReceivedEvent:
        union_image_received_event = ImageReceivedEvent.ImageReceivedEvent()
        union_image_received_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_image_received_event
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

    if event_type_int == EventType.MonitorPowerStartEvent:
        union_plugin_terminate_event = MonitorPowerStartEvent.MonitorPowerStartEvent()
        union_plugin_terminate_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_plugin_terminate_event
    
    if event_type_int == EventType.MonitorPowerStopEvent:
        union_plugin_terminate_event = MonitorPowerStopEvent.MonitorPowerStopEvent()
        union_plugin_terminate_event.Init(event.Event().Bytes, event.Event().Pos)
        return union_plugin_terminate_event

    raise Exception(f"Unrecognized event type {event_type_int}")


def socket_message_to_typed_event(msg: bytearray):
    # Remove the event type byte prefix and then convert to an event.
    # We can only do that with a bytearray, which is mutable, while a bytes object is not, 
    # so first check 
    if type(msg) == bytes:
        # note: this makes an additional copy of the entire bytes object in memory, so will be less performant.
        msg = bytearray(msg)
    b = _remove_event_prefix(msg)
    e = _bytes_to_event(b)
    return _event_to_typed_event(e)
