# # import os
# # from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
# # from ctevents.ctevents import socket_message_to_typed_event,send_image_scored_fb_event
# # import zmq
# # import logging
# # logging.basicConfig(level=logging.INFO)

# # logger = logging.getLogger("Oracle Monitor")
# # PORT = os.environ.get('ORACLE_PLUGIN_PORT', 6011)
# # print("Port oracle")
# # OUTPUT_DIR = os.environ.get('TRAPS_ORACLE_OUTPUT_PATH', "/output/")

# # def get_socket():
# #     # create the zmq context object
# #     context = zmq.Context()
# #     return get_plugin_socket(context, PORT)  

# # def main():
# #     socket = get_socket()
# #     done = False
# #     while not done:
# #         print("Inside while")
# #         message = get_next_msg(socket)
      
# #         logger.info("Got a message from the event socket - Oracle monitor check")
# #         event = socket_message_to_typed_event(message)
# #         #event2 = send_image_scored_fb_event(message)
# #         print("printing event",event,event2)
# #         image_uuid = event.ImageUuid()
# #         #score = event2.scores
       
# #         # label = event.Label()
# #         # score = event.Scores()
# #         # print("Inside oracle", image_uuid,label,score)
        
        

# # if __name__ == '__main__':
# #     main()



# import os
# import zmq
# import uuid
# import logging
# from pyevents.events import get_plugin_socket, get_next_msg, send_quit_command
# from ctevents.ctevents import socket_message_to_typed_event
# from ctevents import ImageScoredEvent, ImageStoredEvent, ImageDeletedEvent
# import csv
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("Oracle Monitor")
# PORT = os.environ.get('ORACLE_PLUGIN_PORT', 6011)
# OUTPUT_DIR = os.environ.get('TRAPS_ORACLE_OUTPUT_PATH', "/output/")
# file_name = "ground_truth.csv"
# SOCKET_TIMEOUT = 2000

# def get_socket():
#     context = zmq.Context()
#     return get_plugin_socket(context, PORT)  


# def main():
#     done = False
#     while not done:
#         socket = get_socket()
#         # try:
#         #     message = get_next_msg(socket)
#             # message = get_next_msg(socket)
#         # except Exception as e:
#         #     # we got a resource temporarily unavailable error; sleep for a second and try again
#         #     if isinstance(e, zmq.error.Again):
#         #         logger.debug(f"Got a zmq.error.Again; i.e., waited {SOCKET_TIMEOUT} ms without getting a message")
#         #         continue
#         #     # we timed out waiting for a message; just check the max time and continue 
#         #     logger.debug(f"Got exception from get_next_msg; type(e): {type(e)}; e: {e}")
#         #     done = True 
#         #     logger.info("Oracle monitoring plugin stopping due to timeout limit...")
#         #     continue
#         message = get_next_msg(socket)
#         logger.info("Got a message from the event socket - Oracle monitor check")
#         event = socket_message_to_typed_event(message)
       
#         if isinstance(event, ImageScoredEvent):
#             uuid = event.ImageUuid()
#             scores = event.ScoresLength()
#             #sc = event.Scores(scores)
#             timestamp = event.EventCreateTs()
#             print("Inside scoring", uuid, scores,timestamp)
#             output_file = os.path.join(OUTPUT_DIR, file_name)
#             # if isinstance(event, NewImageEvent):
#             #     uuid = event.ImageUuid()
#             # if isinstance(event, ImageScoredEvent):
#             #     uuid = event.ImageUuid()
            
#             if not os.path.exists(output_file):
#                 with open(output_file, 'w', newline='') as file:
#                     mapping = csv.writer(file)
#                     field = ["Image count","UUID", "Image name"]
#                     mapping.writerow(field)
#                     mapping.writerow([uuid, scores, timestamp])
#             else:
#                 with open(output_file, 'a', newline='') as file:
#                     mapping = csv.writer(file)
#                     mapping.writerow([uuid, scores, timestamp])
#         elif isinstance(event, ImageStoredEvent):
#             print("Image stored")
#         elif isinstance(event, ImageDeletedEvent):
#             print("Image deleted")
#         else:
#             print(event)


# if __name__ == '__main__':
#     main()
