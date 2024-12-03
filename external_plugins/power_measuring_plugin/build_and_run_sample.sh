#!/bin/bash

# git repo required
# https://github.com/tapis-project/camera-traps
# https://github.com/tapis-project/event-engine.git


camera_traps_home="/media/orin/Orin_vol/camera-traps/camera-traps"
event_engine_home="/media/orin/Orin_vol/camera-traps/event-engine"

REL=0.3.3


# !!! Restart Docker Service !!! Be careful
# sudo systemctl daemon-reload
# sudo systemctl restart docker

# !!!! Remove all images !!!! Be careful
# sudo docker rmi $(sudo docker images -q)

# !!!! Remove all containers !!!! Be careful

if [ $(sudo docker ps -aq |wc -l) -gt 0 ]; then
    sudo docker rm $(sudo docker ps -aq) # remove all containers
fi



# Build the depending images
docker pull python:3.8.10

cd $event_engine_home/pyevents
sudo docker build .  -t tapis/pyevents || exit 1



cd $camera_traps_home/src/python
sudo docker build . --build-arg TRAPS_REL=$REL -t tapis/camera_traps_py:$REL || exit 1


cd $camera_traps_home
sudo docker build . --build-arg TRAPS_REL=$REL -t tapis/camera_traps_engine:$REL || exit 1




# Build External Plugins

cd $camera_traps_home/external_plugins/image_scoring_plugin
sudo docker build . --build-arg REL=$REL -t tapis/image_scoring_plugin_py:$REL || exit 1


cd $camera_traps_home/external_plugins/image_generating_plugin
sudo docker build . --build-arg REL=$REL -t tapis/image_generating_plugin_py:$REL || exit 1



# Build the Power Measurment Plugin
cd $camera_traps_home/external_plugins/power_measuring_plugin
sudo docker build . --build-arg REL=$REL -t tapis/power_measuring_plugin_py:$REL || exit 1






#!!! Testing the Power Measurment Plugin
cd $camera_traps_home/releases/"$REL"_power_test
sudo docker compose up --no-recreate


#!!! or Compose up the release
# cd $camera_traps_home/releases/$REL
# sudo docker compose up --no-recreate
