import datetime
import uuid
import sys
from ctevents.ctevents import _bytes_to_event, _event_to_typed_event
from ctevents.ctevents import _generate_new_image_fb_event, _generate_image_received_fb_event, _generate_image_scored_fb_event, _generate_delete_image_fb_event, _generate_start_plugin_fb_event, _generate_terminating_plugin_fb_event, _generate_terminate_plugin_fb_event, _generate_store_image_fb_event
from ctevents.ctevents import _generate_new_image_fb_with_prefix, _generate_image_received_fb_with_prefix, _generate_store_image_fb_with_prefix, _generate_terminating_plugin_fb_with_prefix, _generate_delete_image_fb_with_prefix, _generate_image_scored_fb_with_prefix, _generate_start_plugin_fb_with_prefix, _generate_terminate_plugin_fb_with_prefix
from ctevents.ctevents import EVENT_TYPE_BYTE_PREFIX


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
    new_image_event = _event_to_typed_event(e)
    
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
    
def test_new_image_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing new image event flatbuffers
    with prefix works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    format = 'jpg'
    with open('labrador-pup.jpg', 'rb') as f:
        image = f.read()
        
    # make a test new image event flattbuffer with prefix
    new_image_fb = _generate_new_image_fb_with_prefix(uuid_str, format, image)  
    
    # check that prefix is the right thing
    assert new_image_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['NEW_IMAGE']

def test_image_received_event_fb():
    """
    A basic test function to check that serializing and deserializing image received event flatbuffers
    works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    format_str = 'jpg'
        
    # make a test image scored event flattbuffer
    image_received_fb = _generate_image_received_fb_event(uuid_str, format_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(image_received_fb)

    # convert the root event object to a typed event (of type new image)
    image_received_event = _event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert image_received_event.ImageUuid() == uuid_str.encode('utf-8')
    assert image_received_event.ImageFormat() == format_str.encode('utf-8')
    now = datetime.datetime.utcnow().isoformat()
    # assert times have the same year --
    assert now[:19] == image_received_event.EventCreateTs().decode('utf-8')[:19]

def test_image_received_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing image received event flatbuffers
    with prefix works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    format = 'jpg'
        
    # make a test new image event flattbuffer with prefix
    new_image_fb = _generate_image_received_fb_with_prefix(uuid_str, format)  
    
    # check that prefix is the right thing
    assert new_image_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['IMAGE_RECEIVED']

def test_image_stored_event_fb():
    """
    A basic test function to check that serializing and deserializing image stored event flatbuffers
    works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    destination = "/data"
    format_str = 'jpg'
        
    # make a test image scored event flattbuffer
    stored_image_fb = _generate_store_image_fb_event(uuid_str, format_str, destination)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(stored_image_fb)

    # convert the root event object to a typed event (of type new image)
    store_image_event = _event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert store_image_event.ImageUuid() == uuid_str.encode('utf-8')
    assert store_image_event.Destination() == destination.encode('utf-8')
    assert store_image_event.ImageFormat() == format_str.encode('utf-8')

def test_image_stored_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing image stored event flatbuffers
    with prefix works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    destination = "/data"
    format_str = 'jpg'

    # make a test image stored event flattbuffer
    stored_image_fb = _generate_store_image_fb_with_prefix(uuid_str, format_str, destination) 
    
    # check that prefix is the right thing
    assert stored_image_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['IMAGE_STORED']
    
def test_delete_image_event_fb():
    """
    A basic test function to check that serializing and deserializing delete image event flatbuffers
    works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    format_str = 'jpg'

    # make a test delete image event flattbuffer
    delete_image_fb = _generate_delete_image_fb_event(uuid_str, format_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(delete_image_fb)

    # convert the root event object to a typed event (of type new image)
    delete_image_event = _event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert delete_image_event.ImageUuid() == uuid_str.encode('utf-8')
    assert delete_image_event.ImageFormat() == format_str.encode('utf-8')

def test_delete_image_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing delete image event flatbuffers
    with prefix works as expected. 
    """
    # create some test data --
    uuid_str = str(uuid.uuid4())
    format_str = 'jpg'

    # make a test new image event flattbuffer
    delete_image_fb = _generate_delete_image_fb_with_prefix(uuid_str, format_str) 
    
    # check that prefix is the right thing
    assert delete_image_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['IMAGE_DELETED']

def test_start_plugin_event_fb():
    """
    A basic test function to check that serializing and deserializing start plugin event flatbuffers
    works as expected. 
    """
    # create some test data --
    plugin_name = "plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test start plugin event flattbuffer
    start_plugin_fb = _generate_start_plugin_fb_event(plugin_name, uuid_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(start_plugin_fb)

    # convert the root event object to a typed event (of type new image)
    start_plugin_event = _event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert start_plugin_event.PluginUuid() == uuid_str.encode('utf-8')
    assert start_plugin_event.PluginName() == plugin_name.encode('utf-8')

def test_start_plugin_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing start plugin event flatbuffers
    with prefix works as expected. 
    """
    # create some test data --
    plugin_name = "plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test start plugin event flattbuffer
    start_plugin_fb = _generate_start_plugin_fb_with_prefix(plugin_name, uuid_str) 
    
    # check that prefix is the right thing
    assert start_plugin_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['PLUGIN_STARTED']

def test_terminating_plugin_event_fb():
    """
    A basic test function to check that serializing and deserializing terminating plugin event flatbuffers
    works as expected. 
    """
    # create some test data --
    plugin_name = "plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test terminating plugin event flattbuffer
    terminating_plugin_fb = _generate_terminating_plugin_fb_event(plugin_name, uuid_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(terminating_plugin_fb)

    # convert the root event object to a typed event (of type new image)
    terminating_plugin_event = _event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert terminating_plugin_event.PluginUuid() == uuid_str.encode('utf-8')
    assert terminating_plugin_event.PluginName() == plugin_name.encode('utf-8')

def test_terminating_plugin_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing terminating plugin event flatbuffers
    with prefix works as expected. 
    """
     # create some test data --
    plugin_name = "plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test terminating plugin event flattbuffer
    terminating_plugin_fb = _generate_terminating_plugin_fb_with_prefix(plugin_name, uuid_str)  

    # check that prefix is the right thing
    assert terminating_plugin_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['PLUGIN_TERMINATING']

def test_terminate_plugin_event_fb():
    """
    A basic test function to check that serializing and deserializing terminate plugin event flatbuffers
    works as expected. 
    """
    # create some test data --
    target_plugin_name = "target_plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test terminate image event flattbuffer
    terminate_plugin_fb = _generate_terminate_plugin_fb_event(target_plugin_name, uuid_str)  
    
    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(terminate_plugin_fb)

    # convert the root event object to a typed event (of type new image)
    terminate_plugin_event = _event_to_typed_event(e)
    
    # check the fields; each should match the previous test data we generated
    assert terminate_plugin_event.TargetPluginUuid() == uuid_str.encode('utf-8')
    assert terminate_plugin_event.TargetPluginName() == target_plugin_name.encode('utf-8')

def test_terminate_plugin_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing terminate plugin event flatbuffers
    with prefix works as expected. 
    """
    # create some test data --
    target_plugin_name = "target_plugin_test"
    uuid_str = str(uuid.uuid4())
        
    # make a test terminate plugin event flattbuffer
    terminate_plugin_fb = _generate_terminate_plugin_fb_with_prefix(target_plugin_name, uuid_str)  

    # check that prefix is the right thing
    assert terminate_plugin_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['PLUGIN_TERMINATE']

def test_image_scored_event_fb():
    """
    A basic test function to check that serializing and deserializing image scored event flatbuffers
    works as expected. 
    """
    # create test data
    scores = [
        {"label": "lab", "probability": 0.95},
        {"label": "golden_retriever", "probability": 0.05},
        {"label": "pug", "probability": 0.012}
    ]
    image_uuid = "8f5f3962-d301-4e96-9994-3bd63c472ce8"
    image_format = 'jpg'

    # make an image scored flatbuffers object
    image_scored_fb = _generate_image_scored_fb_event(image_uuid, image_format, scores)

    # convert the flattbuffer back to a root event object 
    e = _bytes_to_event(image_scored_fb)

    # convert the root event object to a typed event (of type new image)
    image_scored_event = _event_to_typed_event(e)

    # test that image_scored_event has the same data on it as the original input data...
    assert "8f5f3962-d301-4e96-9994-3bd63c472ce8" == image_scored_event.ImageUuid().decode('utf-8')
    assert image_scored_event.ImageFormat() == image_format.encode('utf-8')

    now = datetime.datetime.utcnow().isoformat()
    # assert times have the same year --
    assert now[:4] == image_scored_event.EventCreateTs().decode('utf-8')[:4]

    for i in range(image_scored_event.ScoresLength()):
        # check each field..
        # TODO -- also check label and probability...
        assert image_scored_event.Scores(i).Label().decode('utf-8') == scores[i]['label']
        # print("from fb: " + image_scored_event.Scores(i).Label().decode('utf-8'))
        # print("from py dict: " + scores[i]['label'])
        assert abs(image_scored_event.Scores(i).Probability() - scores[i]['probability']) < 0.1
        # print("from fb: " + str(image_scored_event.Scores(i).Probability()))
        # print("from py dict: " + str(scores[i]['probability']))
    return image_scored_event

def test_image_scored_event_with_prefix():
    """
    A basic test function to check that serializing and deserializing image scored event flatbuffers
    works as expected. 
    """
    # create test data
    scores = [
        {"image_uuid": "8f5f3962-d301-4e96-9994-3bd63c472ce8", "label": "lab", "probability": 0.95},
        {"image_uuid": "8f5f3962-d301-4e96-9994-3bd63c472ce8", "label": "golden_retriever", "probability": 0.05},
        {"image_uuid": "8f5f3962-d301-4e96-9994-3bd63c472ce8", "label": "pug", "probability": 0.012}
    ]
    image_uuid = "8f5f3962-d301-4e96-9994-3bd63c472ce8"
    image_format = 'jpg'

    # make a test image scored event flattbuffer
    image_scored_fb = _generate_image_scored_fb_with_prefix(image_uuid, image_format, scores)

    # check that prefix is the right thing
    assert image_scored_fb[0:2] == EVENT_TYPE_BYTE_PREFIX['IMAGE_SCORED']


if __name__ == "__main__":
    test_new_image_event_fb()
    test_new_image_event_with_prefix()
    test_image_received_event_fb()
    test_image_received_event_with_prefix()
    test_image_scored_event_fb()
    test_image_scored_event_with_prefix()
    test_image_stored_event_with_prefix()
    test_image_stored_event_fb()
    test_delete_image_event_fb()
    test_delete_image_event_with_prefix()
    test_start_plugin_event_fb()
    test_start_plugin_event_with_prefix()
    test_terminating_plugin_event_fb()
    test_terminating_plugin_event_with_prefix()
    test_terminate_plugin_event_fb()
    test_terminate_plugin_event_with_prefix()