# Image: tapis/camera-traps-installer

FROM python:3.12

RUN pip install Jinja2==3.1.4 pyyaml==6.0.1

# Directory where host will be mounted 
RUN mkdir -p /host
# Add a default input file into the container image
ADD example_input.yml /host/input.yml

# Directory of default config files and values for the application 
RUN mkdir /defaults 
ADD defaults.yml /defaults/defaults.yml 
ADD example_images /defaults/example_images

# The installer app itself
RUN mkdir -p /installer
RUN touch /installer/__init__.py 
ADD templates /installer/templates
ADD compile.py /compile.py 
RUN chmod 0777 -R /installer
RUN chmod 0777  /compile.py 

CMD [ "python", "/compile.py" ]