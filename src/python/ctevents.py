import datetime
import uuid
from tokenize import String
import flatbuffers
from gen_events import NewImageEvent
import zmq

# event engine helper lib
from events import get_plugin_socket, get_next_msg, publish_msg, send_quit_command

PYPLUGIN_TCP_PORT = 6000

def _generate_new_image_fb_event(uuid: String, format: String, image: bytearray):
    """Send a new image event over the plugin's ZMQ socket."""
    # create and serialize the individual fields first -----
    # convert ts to string formatted 
    ts = datetime.datetime.utcnow().isoformat()
    builder = flatbuffers.Builder(1024)
    ts_fb = builder.CreateString(ts)
    uuid_fb = builder.CreateString(uuid)
    format_fb = builder.CreateString(format)
    # loop over bytes of image
    NewImageEvent.NewImageEventStartImageVector(builder, len(image))
    for i in reversed(range(len(image))):
        builder.PrependByte(image[i])
    image_fb = builder.EndVector()
    # start the new image event, add the individual fields, then call End() -----
    NewImageEvent.Start(builder)
    NewImageEvent.AddEventCreateTs(builder, ts_fb)
    NewImageEvent.AddImageUuid(builder, uuid_fb)
    NewImageEvent.AddImageFormat(builder, format_fb)
    NewImageEvent.AddImage(builder, image_fb)
    new_image_event = NewImageEvent.End(builder)
    # finish the event
    builder.Finish(new_image_event)
    return builder.Output() # Of type `bytearray`
    
def _bytes_to_new_image_event(data: bytearray):
    """ convert the bytes of a new image event to the event object"""
    

def send_new_image_event(socket, uuid: String, format: String, image: bytearray):
    """ public API for sending a new image event"""
    buf = _generate_new_image_fb_event(uuid, format, image)
    # send the message over the socket
    publish_msg(socket, buf)


uuid_str = str(uuid.uuid4())
format = 'jpg'
with open('labrador-pup.jpg', 'rb') as f:
    image = f.read()    


def test():
    # create the zmq context object
    # context = zmq.Context()

    # socket = get_plugin_socket(context, PYPLUGIN_TCP_PORT)  
    # uuid_str = str(uuid.uuid4())
    # format = 'jpg'
    # with open('labrador-pup.jpg', 'rb') as f:
    #     image = f.read()    
    new_image_fb = _generate_new_image_fb_event(uuid_str, format, image)
    # send_new_image_event(socket, uuid_str, format, image)


if __name__ == "__main__":
    test()    

    