ARG REL=use-build-arg
FROM tapis/camera_traps_py_3.8:$REL

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
RUN chmod +x $HOME/.cargo/env
ENV PATH="/root/.cargo/bin:$PATH"

RUN pip install flatbuffers numpy
RUN cd / && git clone https://github.com/hubblo-org/scaphandre.git
RUN cd /scaphandre && cargo build --release
ENV PATH="/scaphandre/target/release:${PATH}"
RUN mkdir /logs


# ADD input_example.json /input.json
ADD power_measuring_plugin.py /power_measuring_plugin.py

ENTRYPOINT [ "python", "-u", "/power_measuring_plugin.py" ]