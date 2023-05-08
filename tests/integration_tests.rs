use zmq::{Context, Message};
use uuid::Uuid;

use camera_traps::events;
use event_engine::events::{Event};


mod common;

/** This integration test injects a NewImageEvent into a running camera-traps application.
 * At the time of this writing the rust implementation of these camera-traps plugins are 
 * simply chained together:
 * 
 *  - image_recv_plugin
 *  - image_score_plugin
 *  - image_store_plugin
 * 
 * Upon receiving an image event to which they are subscribed, each plugin generates a new
 * output event containing dummy data.
 * 
 * *Set Up*
 *  
 * This test looks for its configuration file path in the TRAPS_INTEGRATION_CONFIG_FILE
 * environment variable.  If this variable is not found, the test looks in the user's
 * ~/traps-integration.toml file.  If a configuration cannot be loaded, the test aborts.
 * 
 * See common/mod.rs for configuration implementation details.
 * See camera-traps/resources/traps-integration.toml for an example configuration.  Here 
 * is an example configuration that processes 10 images:
 * 
 *  iterations = 10
 *  image_input_dir = "~/traps/input"
 * 
 *  [external_plugin_config] 
 *      plugin_name = "ext_image_gen_test_plugin"
 *      id = "d3266646-41ec-11ed-a96f-5391348bab46"
 *      external_port = 6000
 *      subscriptions = [
 *          "PluginTerminateEvent"
 *      ]
 * The input directory should contain at least one .png image file.  The camera-traps
 * application determines where image files are written, if anywhere.  The camera-traps
 * application must also be configured with this external plugin.
 * 
 * *Execution*
 *   
 * The camera-traps application must be running before staring this this test.  An easy
 * way to invoke the application is to type "cargo run" into a terminal where the 
 * current directory is the camera-traps top-level directory.
 * 
 * This test can be easily started in two ways.  The first is to click on the virtual 
 * "Run Test|Debug" prompt that is displayed above the inject_new_image() function
 * definition in Visual Studio.  The other way is to type one of these commands in a 
 * terminal with current directory the camera-traps top-level directory:
 * 
 *  - cargo test --test integration_tests
 * 
 *  - cargo test --test integration_tests -- --show-output
 *  
 * Logging in the camera-traps application terminal will indicate progress.
 */
#[test]
//#[ignore]
fn inject_new_image() {
    // Write to stdout.  To make this appear when running cargo,
    // issue:  cargo test -- --nocapture
    println!("Starting the inject_new_image integration test.");

    // Obtain the integration test configuration.
    let parms = common::get_parms().expect("Unable to retrieve integration test parameter from file.");
    println!("{}", format!("{:#?}", parms));

    // Create this process's zqm context.
    let context = Context::new();

    // Plugin socket utilizes REQ socket type connect to the camera-traps application.
    let socket = context.socket(zmq::REQ).expect("Failed to create socket.");
    let socket_connect_str = "tcp://localhost:".to_string() + &parms.config.external_plugin_config.external_port.to_string();    
    socket.connect(socket_connect_str.as_str()).expect("Failed to connect socket to camera-traps application.");

    // Read the first image file from the input directory.
    let image = common::read_first_file_from_dir(&parms.config.image_input_dir).
                                  expect(("Could not read image file: ".to_string() + 
                                               &parms.config.image_input_dir).as_str()); 

    // Main loop runs a configurable number of iterations.
    let mut iterations = parms.config.iterations;
    while iterations > 0 {
        // Create an event and serialize it for transmission to camera-traps.
        let ev = events::NewImageEvent::new(Uuid::new_v4(), 
                                                           "png".to_string(), 
                                                           image.clone());
        let bytes = match ev.to_bytes() {
            Ok(v) => v,
            Err(e) => {
                // Game over.
                panic!("{}", e.to_string());
            } 
        };

        // Send the event.
        socket.send(bytes, 0).expect("Failed to send byte array to camera-traps application.");

        // Get the reply
        let mut reply = Message::new();
        socket.recv(&mut reply, 0).expect("Failed on reply.");

        // Decement the iteration count.
        iterations -= 1;
    }

    // Disconnect from the camera-traps application.
    socket.disconnect(socket_connect_str.as_str()).expect("Failed to close socket.");

}