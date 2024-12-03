#just used for help me remember usful command lines



# docker build --build-arg REL=latest -t test_power .
# docker run -it test_power:latest
# docker cp bold_herschel:/ /home/murphie/Project/cameraTrap/inspect_power
# docker build -t power_measuring_plugin .


sudo systemctl daemon-reload
sudo systemctl restart docker


sudo docker rmi $(sudo docker images -q) # remove all images


--build-arg TRAPS_REL=

sudo docker rm $(sudo docker ps -aq) # remove all containers


sudo docker build . --build-arg TRAPS_REL=0.3.3 -t tapis/camera_traps_engine:0.3.3

sudo docker run --rm -it tapis/camera_traps_engine:0.3.3 /bin/sh


sudo docker build . --build-arg REL=0.3.3 -t tapis/image_generating_plugin_py:0.3.3

sudo docker build . --build-arg REL=0.3.3 -t tapis/camera_traps_py:0.3.3



sudo docker run --rm -it tapis/image_scoring_plugin_py /bin/sh



sudo docker build . --build-arg REL=0.3.3 -t tapis/power_measuring_plugin_py:0.3.3

sudo docker run --rm -it --entrypoint /bin/bash -v /run/jtop.sock:/run/jtop.sock tapis/power_measuring_plugin_py:0.3.3 


sudo docker exec -it `sudo docker ps -q`  /bin/bash
sudo docker exec -it d290ad9f18dc  /bin/bash