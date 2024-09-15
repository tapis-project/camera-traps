import os 
import shutil
import sys 

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
    
    # the powerjoular backend requires the docker socket to function:
    if vars.get("power_monitor_backend") == 'powerjoular':
        vars['power_monitor_mount_docker_socket'] = True
    
    # the model id must be passed if trying to use a different model from the default 
    if vars.get("use_model_url"):
        if not vars.get("model_id"):
            print(f"ERROR: The model_id parameter is required when use_model_url is True (i.e., when using a custom model.)")
            sys.exit(1)
        if not vars.get("model_url"):
            print(f"ERROR: The model_url parameter is required when use_model_url is True")
            sys.exit(1)
            

    # Add the installer's UID and GID
    vars["uid"] = uid
    vars["gid"] = gid 

    # Add the host install path 
    install_host_path = os.environ.get("INSTALL_HOST_PATH")
    vars["install_host_path"] = install_host_path
    
    print(f"Merged variables: {vars}")
    return vars 


def download_model_by_id(vars, full_install_dir):
    """
    Download a model based on its id and put it in the install dir.
    """
    # download the model .pt file for recognized model id's 
    model_id = vars.get("model_id")
    # this model is the default one and does not need to be downloaded
    if model_id == "4108ed9d-968e-4cfe-9f18-0324e5399a97-model":
        print("Default model, not downloading...")
        return
    model_url = None
    # this is model "5b"
    # if model_id == '4108ed9d-968e-4cfe-9f18-0324e5399a97-model':
    #     model_url = "https://github.com/ICICLE-ai/camera_traps/raw/main/models/md_v5b.0.0.pt"
    # this is model "5-optimized"
    # elif model_id == '665e7c60-7244-470d-8e33-a232d5f2a390-model':
    #     model_url = "https://github.com/ICICLE-ai/camera_traps/raw/main/models/mdv5_optimized.pt"
    # this is model "5a_ena"
    # elif model_id == '2e0afb62-349d-46a4-9fc7-5f0c2b9e48a5-model':
    #     model_url = "https://github.com/ICICLE-ai/camera_traps/blob/main/models/md_v5a.0.0_ena.pt"
    # # this is model "5c"
    # elif model_id == '04867339-530b-44b7-b66e-5f7a52ce4d90-model':
    #     model_url = "URL_TBD"
    #     print(f"ERROR: Model 5c not yet available. Exiting...")    
    #     sys.exit(1)
    # else:
    # try to look up the model URL from CKN
    print(f"Checking CKN for the URL to the pt file...")
    url = f"https://ckn.d2i.tacc.cloud/patra/download_url?model_id={model_id}"
    try:
        rsp = requests.get(url)
        rsp.raise_for_status()
    except Exception as e:
        print(f"ERROR: Could not lookup model URL from CKN; details: {e}. exiting...")
        sys.exit(1)
    try:
        data = rsp.json()
    except Exception as e:
        print(f"ERROR: Could not parse JSON from CKN response; details: {e}. exiting...")
        sys.exit(1)
    print(f"Response from CKN: {data}")
    error = data.get("error")
    if error:
        print(f"ERROR: Got error from CKN response; details: {error}. exiting...")
        sys.exit(1)
    try:
        model_url = rsp.json().get("download_url")
    except Exception as e:
        print(f"ERROR: Could not get model URL from CKN response; details: {e}. exiting...")
        # print(f"Requests path: {requests.__file__}")
        # print(f"Requests lib contents: {dir(requests)}")
        sys.exit(1)
    print(f"Got URL for model from CKN; URL: {model_url}")
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


def compile_templates(vars, full_install_dir):
    """
    Compile all the templates to the `full_install_dir` using the `vars` dictionary. 
    """
    # create the jinja environment object
    env = Environment(
        loader=PackageLoader("installer"),
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