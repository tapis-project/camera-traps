#!/bin/bash
# Usage: ./install /path/to/directory input.yml
# The /path/to/directory argument should be an absolute path where the installer will install
# the files and where it can find the input.yml file (specified as the second argument) as well 
# as any other relative files and/or directories specified in the input.yml

# get the UID and GID of the current user
export uid=$(id -u)
export gid=$(id -g)

# run the installer container as the host UID and GID, mounting the the host file system as passed

# in argument 1 and the INPUT_FILE environment variable, as passed in argument 2.
input_file=${2:-install_config.yml}

    docker run -it --rm --user $uid:$gid -v $1:/host/ -e INSTALL_HOST_PATH=$1 -e INPUT_FILE=$input_file tapis/camera-traps-installer