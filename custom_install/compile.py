import os 
import shutil
import sys 

from jinja2 import Environment, PackageLoader, select_autoescape
import yaml


def get_defaults():
    """
    Read the defaults from the 
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
            print(f"Got input data: {input_data}")
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

    print(f"Writing output to the following directory: {input_install_dir}")
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
    
    # Add the installer's UID and GID
    vars["uid"] = uid
    vars["gid"] = gid 

    # Add the host install path 
    install_host_path = os.environ.get("INSTALL_HOST_PATH")
    vars["install_host_path"] = install_host_path
    
    print(f"Merged variables: {vars}")
    return vars 


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
    generate_additional_directories(vars, full_install_dir)
    compile_templates(vars, full_install_dir)
    


if __name__ == '__main__':
    main()