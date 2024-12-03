#!/bin/bash

# The current directory is the releases/<releaseNum>/integration-test; the directory from
# which we execute the integration tests is the top-level camera-traps directory.  The 
# traps-integration.toml file is also configured for top-level directory.
cd ../../..

# Override the default configuration file.
export TRAPS_INTEGRATION_CONFIG_FILE='releases/0.3.1/integration-test/traps-integration.toml'

# Let cargo run the integration test.
cargo test --test integration_tests -- --show-output