Camera Traps Custom Installer 
==============================

This directory contains the camera traps installer program to simplify the process of creating custom installations of the Camera Traps software based on a configuration file.


Basic Usage
-----------
To use the installer, execute the `install.sh` script within this directory,
passing two positional arguments:

* Host directory: Absolute path on the host where the 
  installer will look for input files and install 
  Camera Traps.
* Input YAML file: path relative to Host directory where 
  an input YAML file containing the configurations for 
  the installation. This input is *optional*, the default
  value is install_config.yml

Example invocation:

```
 $ ./install.sh /home/jstubbs/tmp/ct-installer my-input.yml
```

In the example above, the installer will look for a file
called `my-input.yml` with absolute path `/home/jstubbs/tmp/ct-installer/my-input.yml` with the configurations 
for the installation. 

Example contents of my-input.yml

```
install_dir: test
use_gpu_in_scoring: true
```

The values in `my-input.yml` override defaults provided 
by the installer. In the example above, the following
will happen:

1. Camera Traps installer will install the main docker-compose.yml file and all necessary directories and 
additional files within the `test` directory of 
`/home/jstubbs/tmp/ct-installer`. 
2. The image scoring plugin will be configured to use 
GPUs on the host machine. 
3. All other default configurations will be used. 
   

See the following sections for details about the configurations available and defaults used.  


Required Configuration
----------------------
The Input YAML file must provide values for the following
fields:

* `install_dir`: Relative path on the host (relative to 
  Host directory) where the 
  Camera Traps files will be installed.
  
  Example: `test`


Important Optional Configurations
----------------------------------

* `ct_version`: The release version (i.e., image tag) for 
  the camera traps software container images.

  * Example: 0.3.3

* `run_containers_as_user`: Whether to run all containers 
  as the user's (i.e., the installer's) UID and GID. (Default: true)

  * Example: false

* `use_gpu_in_scoring`: Whether to use GPUs with the 
  Image Scoring pluging. Note that
  the NVIDIA drivers must be installed, the NVIDIA container toolkit installed, and 
  Docker must be configured to use it. See the main README for details on hardware requirements. (Default: false)

  * Example: true

* `image_store_save_threshold`: The minimum confidence 
  threshold for storing an image in full format.

  * Example: 0.7
 
* `image_store_reduce_save_threshold`: The minimum 
  confidence threshold for storing an image in reduces/compressed format.

  * Example: 0.4

* `device_id`: The id of the device where the camera traps code will be installed. For example, 
  this could be the id of a ChameleonCloud node or a TACC IoT device. By default, the string
  `AAAAAAAAAAAAAAAAAAAA` is assigned for cases where the device id will not be needed. 


**Source Images**

One can control the source of images used for the 
simulation in various ways. By default, the installer 
users a pre-bundled set of example image. See below:

* `use_bundled_example_images`: Whether to use a set of 
  bundled example images as the source of the input image.
  When true, the use_image_directory and use_image_url settings are ignored. (Default: true)

* `use_image_directory`: Whether to use a directory on 
  the host as the source of the input images. If 
  set to true, the source_image_dir variable must also be set. If set to false, a URL to a tar.gz file of images must be provided by setting use_image_url and source_image_url. (Default: false)

* `source_image_dir`: Host directory containing example   
  images to be used for the simulation. Only used if 
  use_image_directory is set to true;

  * Example: example_images
  
* `use_image_url`: Whether to use a URL to a tar.gz file 
  of images as the source of the input images. If 
  set to true, the source_image_url variable must also be set. 

  * Example: true

* `source_image_url`: URL to a tar.gz file of images to 
  use as the input images. 

  * Example: `https://lilablobssc.blob.core.windows.net/snapshot-safari/KGA/KGA_S1.lila.zip`

*  `use_custom_ground_truth_file_url`: Whether to use a custom ground truth file with the dataset. 
  This only needs to be set when using a non-standard dataset. Default is false. When setting to true,
  must also set the `custom_ground_truth_file_url` variable.

* `custom_ground_truth_file_url`: URL to a custom ground truth file to download. This variable is only
  used if `use_custom_ground_truth_file_url` is set to true. 

**Specifying the Model**

* `use_custom_model_type`: Use one of the pre-defined model types. When true, must also specify `model_type`. 
  (Default: false).

  * Example: true 

* `model_type`: Specify the custom model type to use. Currently supported values are: `1`, `2`, `3`. 
  This is a work in progress, more details coming. 

* `use_model_url`: Use a URL to a compatible ML model .pt 
  file. Will be downloaded at the start of the scoring plugin execution. If true, must also specify model_url. 

  * Example: false

* `model_url` (*currently not supported*): The URL to a model to download. Only used if use_model_url is true.

  * Example: N/A
 

**Integrating with CKN**

* `deploy_ckn`: Whether to deploy the CKN capture daemon; required for integration with CKN. Default is false.

  * Example: true

* `ckn_kafka_broker_address`: The remote address of the CKN Kafka broker. 
  
  * Example: `129.114.35.150`

* `ckn_kafka_broker_port`: The remote port of the CKN Kafka broker.
  
  * Example: 9092

* `experiment_id`: An id to associate all measurements from this execution with. For example, a Tapis Job id.
  By default, this variable is set to none.

* `user_id`: The user id of the owner of the experiment. By default, this variable is set to none.


All Configurations 
------------------

This is a complete list of all possible configurations.

* `install_dir`: Relative path on the host (relative to 
  Host directory) where the 
  Camera Traps files will be installed.   ** Note ** all config paths are relative to this directory. 
  
  Example: `test`

* `ct_version`: The release version (i.e., image tag) for the camera traps software container images 

  * Example: 0.3.3

* `host_config_dir`: Path on the host where configuration 
  directory resides. 

  * Example: ./config 
  
* `use_host_pid`: Whether to start all plugin containers 
  in the host PID namespace.

  * Example: true

* `run_containers_as_user`: Whether to run all containers 
  as the user's (i.e., the installer's) UID and GID

  * Example: true
  
* `image_generating_monitor_power`: Whether to monitor 
  the power usage of the image generating plugin. Default: true 

  * Example: false
  
* `use_bundled_example_images`: Whether to use a set of 
  bundled example images as the source of the input image.
  When true, the use_image_directory and use_image_url settings are ignored.

* `use_image_directory`: Whether to use a directory on 
  the host as the source of the input images. If 
  set to true, the source_image_dir variable must also be set. If set to false, a URL to a tar.gz file of images must be provided by setting use_image_url and source_image_url. 

  * Example: true

`source_image_dir`: Host directory containing example 
  images to be used for the simulation. Only used if 
  use_image_directory is set to true;

  * Example: example_images
  
* `use_image_url`: Whether to use a URL to a tar.gz file 
  of images as the source of the input images. If 
  set to true, the source_image_url variable must also be set. 

  * Example: true

* `source_image_url`: URL to a tar.gz file of images to 
  use as the input images. 

  * Example: `https://lilablobssc.blob.core.windows.net/snapshot-safari/KGA/KGA_S1.lila.zip`

* `use_gpu_in_scoring`: Whether to use GPUs with the 
  Image Scoring pluging. Note that
  the NVIDIA drivers must be installed, the NVIDIA container toolkit installed, and 
  Docker must be configured to use it. See the main README for details on hardware requirements.

  * Example: true
  
* `host_output_dir`: Host directory where output 
 directories will be written. (relative to installation
 directory)

  * Example: output

* `images_output_dir`: Host directory within the 
  host_output_dir where the output images will be written. (Relative to `host_output_dir`)

  * Example: images_output_dir


* `image_store_save_threshold`: The minimum confidence 
  threshold for storing an image in full format.

  * Example: 0.7
 
* `image_store_reduce_save_threshold`: The minimum 
  confidence threshold for storing an image in reduces/compressed format.

  * Example: 0.4
  
   
* `oracle_plugin_output_dir`: Host directory within the 
  host_output_dir where the oracle_plugin's outputs will be written. (Relative to `host_output_dir`)

  * Example: oracle_output_dir

* `image_generating_log_level`: Log level for image 
  generating plugin.  

  * Example: DEBUG, INFO 

* `image_scoring_plugin_image`: The image to use for the 
  image scoring plugin, not including the tag

  * Example: tapis/image_scoring_plugin_py_3.8
  
* `image_scoring_log_level`: Log level for image scoring 
  plugin.  

  * Example: DEBUG, INFO 

* `image_scoring_monitor_power`: Whether to monitor the 
  power usage of the image scoring plugin. Default: true 

  * Example: false

* `image_scoring_crop_images`: Whether to crop images as 
  part of the image scoring ML pipeline. (Default: false)

  * Example: true
 
* `image_scoring_generate_bounding_boxes`: Whether to 
  generate images with bounding boxes as part of the image scoring ML pipeline.

  * Example: false
 
* `use_custom_model_type`: Use one of the pre-defined model types. When true, must also specify `model_type`. 
  (Default: false).

  * Example: true 

* `model_type`: Specify the custom model type to use. Currently supported values are: `1`, `2`, `3`. 
  This is a work in progress, more details coming. 

* `use_model_url`: Use a URL to a compatible ML model .pt 
  file. Will be downloaded at the start of the scoring plugin execution. If true, must also specify model_url. 

  * Example: false

* `model_url` (*currently not supported*): The URL to a model to download. Only used if use_model_url is true.

  * Example: N/A
 
* `run_power_monitor_privileged`: Whether to run the 
  power monitor plugin container in privileged mode. Note: this is required 
  to read the Intel RAPL (Linux Powercap) interface and power monitor backends may not function without it. (Default: true)

  * Example: false 

* `use_gpu_in_power_monitoring`: Whether to use GPUs with 
  the Power Monitroing pluging. At this time, there is no need to 
  use GPUs in Power Monitoring, even if using them in Image Scoring, but this could change in a future release. 
  Note that the NVIDIA drivers must be installed, the NVIDIA container toolkit installed, and 
  Docker must be configured to use it. See the README for details on hardware requirements. (Default: false)

  * Example: true
  
* `power_monitor_log_level`: Log level for power 
  monitoring plugin.

  * Example: DEBUG, INFO 
  
* `power_monitor_backend`: The backend to use for 
  measuring power. 

  * Example: powerjoular, scaphandre

* `power_plugin_monitor_power`: Whether to monitor the 
  power of the power monitoring plugin itself. (Default: true)

  * Example: false 

* `power_output_dir`: Host directory within the 
  host_output_dir where the output of the power plugin will be written. (Relative to `host_output_dir`)

  * Example: power_output_dir

* `power_monitor_mount_docker_socket`: Whether to mount 
  the docker socket into the power monitor plugin container.
  Required when using the powerjoular backend. (Default: true).

  * Example: false

* `oracle_plugin_image`: The image to use for the oracle 
  plugin, not including the tag. (Default: tapis/oracle_plugin)

  * Example: tapis/oracle_plugin
