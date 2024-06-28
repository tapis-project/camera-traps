ARG REL=use-build-arg
FROM tapis/camera_traps_py:$REL

# FROM tapis/camera_traps_py_3.8


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


# ADD input_example.json /input.json
ADD power_measuring_plugin.py /power_measuring_plugin.py
ADD jtop_backend.py /jtop_backend.py
ADD scaphandre_backend.py /scaphandre_backend.py
ADD generate_power_summary.py /generate_power_summary.py
ADD validate_schemas.py /validate_schemas.py 
ADD powerjoular_backend.py /powerjoular_backend.py 

RUN chmod -R 0777 /* || true 

ENV TRAPS_TEST_POWER_FUNCTION=1

ENTRYPOINT [ "python", "-u", "/power_measuring_plugin.py" ]
