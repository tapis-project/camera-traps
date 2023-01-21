# Image: tapis/camera_traps_engine

# -------------------
# First build phase: In this phase we do the build for release with an intermedidate layer that caches the dependencies
# --------------------
FROM rust:1.61 as builder

# install libzmq
RUN USER=root apt-get update && apt-get install -y libzmq3-dev

# To allow us to build and cache only the dependencies, we'll start by creating a "dummy" camera-traps
# cargo project, copy the manifests, and build 
RUN USER=root cargo new camera-traps

WORKDIR /camera-traps

# copy manifests
COPY Cargo.lock ./Cargo.lock
COPY Cargo.toml ./Cargo.toml

# build and cache only the dependencies
RUN cargo build --release
# remvove any dummy source code
RUN rm src/*.rs 

# Now we copy our actual application source code
COPY src ./src

# Build for release 
# on the very first build, this doesn't exist, so have to comment it out or use the "|| true" construction.
RUN rm ./target/release/deps/camera-traps* || true
RUN cargo build --release


# --------------------
# Second build phase: Final base image. This is image will only include the minimum binary and confgis
# --------------------
FROM debian:buster-slim

# # still need to install zmq
RUN USER=root apt-get update && apt-get install -y libzmq3-dev

# copy the build artifact from the build stage
RUN mkdir /resources
COPY --from=builder /camera-traps/target/release/camera-traps .
# copy default configs
COPY resources/log4rs.yml /resources/log4rs.yml
COPY resources/traps.toml /root/traps.toml 
# set the startup command to run camera-traps binary
CMD ["./camera-traps"]
