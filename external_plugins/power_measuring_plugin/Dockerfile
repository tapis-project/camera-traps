ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL

# FROM tapis/camera_traps_py_3.8

RUN apt update && apt install -y sudo 
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
RUN chmod +x $HOME/.cargo/env
ENV PATH="/root/.cargo/bin:$PATH"
RUN chmod -R 0777 /* || true

# RUN pip install flatbuffers numpy
# RUN pip install jetson-stats

RUN cd / && git clone https://github.com/hubblo-org/scaphandre.git
RUN cd /scaphandre && cargo build --release
ENV PATH="/scaphandre/target/release:${PATH}"

ADD requirements.txt /requirements.txt
RUN pip install -r requirements.txt 

RUN mkdir /logs


RUN echo 'ALL            ALL = (ALL) NOPASSWD: ALL' >> /etc/sudoers
RUN chown root:root /usr/bin/sudo && chmod 4755 /usr/bin/sudo
RUN chmod 644 /usr/lib/sudo/sudoers.so
RUN chmod 0755 /etc/sudoers
RUN chown -R root /usr/lib/sudo
RUN chmod -R a-w /etc/sudoers.d

ADD power_measuring_plugin.py /power_measuring_plugin.py
ADD jtop_backend.py /jtop_backend.py
ADD scaphandre_backend.py /scaphandre_backend.py
ADD generate_power_summary.py /generate_power_summary.py
ADD validate_schemas.py /validate_schemas.py 
ADD powerjoular_backend.py /powerjoular_backend.py 

RUN chmod -R 0777 /power_measuring_plugin.py /jtop_backend.py /scaphandre_backend.py /generate_power_summary.py /validate_schemas.py /powerjoular_backend.py /logs || true 

ENV TRAPS_TEST_POWER_FUNCTION=1

# Run power measuring with sudo so that it can execute privledged commands even when the container is run as a 
# non-privileged user 
ENTRYPOINT [ "sudo", "-E", "python", "-u", "/power_measuring_plugin.py" ]
