import os 
import shutil
import sys 
import json

from jinja2 import Environment, PackageLoader, select_autoescape
import requests
import yaml


def get_defaults():
    """
    Read the defaults from the defaults file. 
    """
    # Container path to defaults file yaml file and return a Python dictionary. 
    defaults_file_path= "/defaults/defaults.yml"
    try:
        with open(defaults_file_path, 'r') as f:
            default_data = yaml.safe_load(f)
            print(f"Got defaults: {default_data}")
    except Exception as e:
        print(f"ERROR: Could not load defaults yaml file from path {defaults_file_path}; error: {e}")
        print("Exiting...")
        sys.exit(1)
    return default_data


def get_inputs():
    """
    Get the user-provided inputs and create the installation directory. 
    """
    # get input file 
    input_file_path = os.path.join("/host", os.environ.get("INPUT_FILE", "input.yml"))
    try:
        with open(input_file_path, 'r') as f:
            input_data = yaml.safe_load(f)
            print(f"\nGot input data: {input_data}")
    except Exception as e:
        print(f"ERROR: Could not load input yaml file from path {input_file_path}; error: {e}")
        print("Exiting...")
        sys.exit(1)

    if not "install_dir" in input_data:
        print("\n\nERROR: The 'install_dir' input is required.")
        print("install_dir: Absolute path to directory on the host where compiled templtes files will be installed.")
        print("Exiting...")
        sys.exit(1)

    input_install_dir = input_data["install_dir"]
    full_install_dir = os.path.join("/host", input_install_dir)

    print(f"Output will be written to the following directory: {input_install_dir}")
    if not os.path.exists(full_install_dir):
        try:
            os.makedirs(full_install_dir)
        except Exception as e:
            print(f"ERROR: Could not create output directory; error: {e}")
            print("Exiting...")
            sys.exit(1)
    return input_data, full_install_dir


def get_vars(input_data, default_data):
    """
    This function uses the inputs and defaults to produce a final dictionary, `vars`, of variables 
    to use to compile the templated. Values in input_data override those in default_data. Additionally,
    some values will be changed to meet program requirements. 
    """
    # override defaults with inputs 
    vars = { **default_data, **input_data }
    
    # add the user's UID and GID -- the installer container process runs as the actual system user
    try:
        uid = os.getuid()
        gid = os.getgid()
    except Exception as e:
        print(f"ERROR: could not determine uid and gid; error: {e}")
        print("Exiting...")
        sys.exit(1)
    
    demo_defaults = {'deploy_image_generating': False,
                     'deploy_image_detecting': True,
                     'deploy_reporter': True,
                     'deploy_ckn': False,
                     'deploy_ckn_mqtt': True,
                     'deploy_power_monitoring': False,
                     'deploy_oracle': False,
                     'inference_server': True}
    simulation_defaults = {'deploy_image_generating': True,
                           'deploy_image_detecting': False,
                           'deploy_reporter': False,
                           'deploy_ckn': True,
                           'deploy_ckn_mqtt': False,
                           'deploy_oracle': True,
                           'inference_server': False}

    if vars.get("mode") == 'demo':
        vars = { **default_data, **demo_defaults, **input_data }
    elif vars.get("mode") == 'simulation':
        vars = { **default_data, **simulation_defaults, **input_data }

    # the powerjoular backend requires the docker socket to function:
    if vars.get("power_monitor_backend") == 'powerjoular':
        vars['power_monitor_mount_docker_socket'] = True

    if vars.get("deploy_power_monitoring") == False:
        vars['image_generating_monitor_power'] = False
        vars['image_scoring_monitor_power'] = False
        vars['power_plugin_monitor_power'] = False

    if not vars.get('download_model'):
        vars['download_model'] = not vars.get('inference_server')
    
    # the model id must be passed if trying to use a different model from the default 
    if vars.get("use_model_url"):
        if not vars.get("model_id"):
            print(f"ERROR: The model_id parameter is required when use_model_url is True (i.e., when using a custom model.)")
            sys.exit(1)
        if not vars.get("model_url"):
            print(f"ERROR: The model_url parameter is required when use_model_url is True")
            sys.exit(1)
        vars['local_model_path'] = './md_v5a.0.0.pt'
    elif vars.get("local_model_path"):
        vars['download_model'] = False
        vars['mount_model_pt'] = True
    elif vars.get("model_id"):
        vars['local_model_path'] = './md_v5a.0.0.pt'
            

    # get the correct image scoring plugin image name
    if vars.get("inference_server"):
        vars['image_scoring_plugin_image'] = 'tapis/image_scoring_plugin_server_py_3.8'
    elif vars.get("use_ultralytics"):
        vars['image_scoring_plugin_image'] = 'tapis/image_scoring_plugin_ultralytics_py_3.8'
    else:
        vars['image_scoring_plugin_image'] = 'tapis/image_scoring_plugin_yolov5_py_3.8'

    # Add the installer's UID and GID
    vars["uid"] = uid
    vars["gid"] = gid 

    # Determine operating system
    if sys.platform.startswith('linux'):
        vars['OS'] = 'linux'
    elif sys.platform.startswith('darwin'):
        vars['OS'] = 'macos'
    elif sys.platform.startswith('nt'):
        vars['OS'] = 'windows'
    else:
        vars['OS'] = 'unknown'

    # Add the host install path 
    install_host_path = os.environ.get("INSTALL_HOST_PATH")
    vars["install_host_path"] = install_host_path
    
    print(f"Merged variables: {vars}")
    return vars 

def get_urls_from_ckn(model_id):
    """
    Given a model card ID, extract the download URL and inference labels URL.
    """
    if model_id.endswith("-model"):
        model_id = model_id[:-6]
    patra_download_endpoint = f"https://ckn.d2i.tacc.cloud/patra/download_mc?id={model_id}"

    response = requests.get(patra_download_endpoint)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data. Status code: {response.status_code}")

    try:
        data = response.json()
        if isinstance(data, str):
            data = json.loads(data)
    except ValueError as e:
        raise Exception("Error parsing JSON response") from e

    ai_model = data.get("ai_model", {})
    download_url = ai_model.get("location")
    inference_labels_url = ai_model.get("inference_labels")
    return download_url, inference_labels_url

def download_model_by_id(vars, full_install_dir):
    """
    Download a model based on its id and put it in the install dir.
    """
    if vars.get("download_model") == False:
        return
    # download the model .pt file for recognized model id's 
    model_id = vars.get("model_id")
    # this model is the default one and does not need to be downloaded
    # download for inference server even if default
    #if model_id == "41d3ed40-b836-4a62-b3fb-67cee79f33d9-model":
    #    print("Default model, not downloading...")
    #    return
    model_url = None
    label_url = None
    print(f"Checking CKN for the URL to the pt file...")
    model_url, label_url = get_urls_from_ckn(model_id)
    print(f"Got URL for model from CKN; URL: {model_url}")
    print(f"Got URL for labels from CKN; URL: {label_url}")
    # if we have a model URL, then we download it so it can be mounted 
    if model_url:
        # download model
        try:
            rsp = requests.get(model_url)
            rsp.raise_for_status()
        except Exception as e:
            print(f"ERROR: could not download model at URL {model_url}; details: {e}")
            sys.exit(1)
        # we always save the file to the same file name, md_v5a.0.0.pt, because this is "hard coded"
        # within the megadetector Python source code
        model_file_install_path = os.path.join(full_install_dir, "md_v5a.0.0.pt")
        # save it to install directory 
        with open(model_file_install_path, "wb") as f:
            f.write(rsp.content) 
        vars["mount_model_pt"] = True   
    if label_url:
        # download labels
        try:
            rsp = requests.get(label_url)
            rsp.raise_for_status()
        except Exception as e:
            print(f'Error could not download model labels at URL {label_url}; details: {e}')
            sys.exit(1)
        label_file_install_path = os.path.join(full_install_dir, 'label_mapping.json')
        # save it to install directory
        with open(label_file_install_path, 'wb') as f:
            f.write(rsp.content)
        vars["mount_labels"] = True   

def compile_templates(vars, full_install_dir):
    """
    Compile all the templates to the `full_install_dir` using the `vars` dictionary. 
    """
    # create the jinja environment object
    env = Environment(
        loader=PackageLoader("installer"),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=select_autoescape()
    )

    # compile the docker-compose template
    compose_template = env.get_template("docker-compose.yml")
    print("Got docker-compose template, compiling..\n\n")

    with open(os.path.join(full_install_dir, "docker-compose.yml"), "w") as f:
        f.write((compose_template.render(**vars)))
    
    # create the config directory in the install directory
    install_config_dir = os.path.join(full_install_dir, "config")
    if not os.path.exists(install_config_dir):
        os.makedirs(install_config_dir)
    # compile all files in the config directory
    for p in os.listdir("/installer/templates/config"):
        template = env.get_template(os.path.join("config", p))
        with open(os.path.join(install_config_dir, p), "w") as f:
            f.write((template.render(**vars)))


def generate_additional_directories(vars, full_install_dir):
    """
    Generate the output directories and other assets required for the compose file
    """
    # deal with source images 
    # if the user wants to use the bundled example images, we ignore all other inputs and copy the 
    # bundled images to the install directory.
    if vars["use_bundled_example_images"]:
        # copy images to the install directory
        try:
            shutil.copytree("/defaults/example_images", os.path.join(full_install_dir, "example_images"))
        except Exception as e:
            print(f"ERROR: Could not copy bundled example images; error: {e}")
            print("Exiting...")
            sys.exit(1)
        vars["source_image_dir"] = "example_images"
        # also need to copy the ground truth file
        try:
            shutil.copy("/defaults/ground_truth.csv", os.path.join(full_install_dir, "ground_truth.csv"))
        except Exception as e:
            print(f"ERROR: Could not copy example images ground_truth.csv; error: {e}")
            print("Exiting...")
            sys.exit(1)
        print(f"Using example_images for source_image_dir")
    
    elif vars["use_image_directory"]:
        if not vars.get("source_image_dir"):
            print(f"ERROR: source_image_dir is required when setting use_image_directory to true")
            print("Exiting...")
            sys.exit(1)
        full_image_dir = os.path.join(full_install_dir, vars.get("source_image_dir"))
        if not os.path.exists(full_image_dir):
            print(f"ERROR: source_image_dir must be a relative path to the install directory and must already exist; the computed path ({full_image_dir}) does not exist.")
            print("Exiting...")
            sys.exit(1)
    elif vars["use_image_url"]:
        if not vars.get("source_image_url"):
            print(f"ERROR: source_image_url is required when setting use_image_url to true")
            print("Exiting...")
            sys.exit(1)
        print(f"Using URL for images: {vars['source_image_url']}")


    # create output directories if they do not exist     
    images_output_dir = os.path.join(full_install_dir, vars["images_output_dir"])

    if not os.path.exists(images_output_dir):
        os.makedirs(images_output_dir)
    
    oracle_plugin_output_dir = os.path.join(full_install_dir, vars["oracle_plugin_output_dir"])
    if not os.path.exists(oracle_plugin_output_dir):
        os.makedirs(oracle_plugin_output_dir)

    power_output_dir = os.path.join(full_install_dir, vars["power_output_dir"])
    if not os.path.exists(power_output_dir):
        os.makedirs(power_output_dir)

    detection_output_dir = os.path.join(full_install_dir, vars["detection_reporter_plugin_output_dir"])
    if not os.path.exists(detection_output_dir):
        os.makedirs(detection_output_dir)
    

def main():
    """ 
    Main loop for generating a custom installation directory for the Camera Traps application.
    """
    default_data = get_defaults()
    input_data, full_install_dir = get_inputs()
    vars = get_vars(input_data, default_data)
    download_model_by_id(vars, full_install_dir)
    generate_additional_directories(vars, full_install_dir)
    compile_templates(vars, full_install_dir)
    


if __name__ == '__main__':
    main()
