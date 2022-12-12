use zmq::{Context, Message};
use uuid::Uuid;

use camera_traps::events;
use event_engine::events::{Event};


mod common;

#[test]
fn inject_new_image() {
    // Write to stdout.  To make this appear when running cargo,
    // issue:  cargo test -- --nocapture
    println!("Starting the inject_new_image integration test.");

    // Obtain the integration test configuration.
    let parms = common::get_parms().expect("Unable to retrieve integration test parameter from file.");
    println!("{}", format!("{:#?}", parms));

    // Create this process's zqm context.
    let mut context = Context::new();

    // Plugin socket utilizes REQ socket type connect to the camera-traps application.
    let socket = context.socket(zmq::REQ).expect("Failed to create socket.");
    let socket_connect_str = "tcp://localhost:".to_string() + &parms.config.external_plugin_config.external_port.to_string();    
    socket.connect(socket_connect_str.as_str()).expect("Failed to connect socket to camera-traps application.");

    // Main loop runs a configurable number of iterations.
    let mut iterations = parms.config.iterations;
    while iterations > 0 {
        // Create an event and serialize it for transmission to camera-traps.
        let ev = events::ImageReceivedEvent::new(Uuid::new_v4());
        let bytes = match ev.to_bytes() {
            Ok(v) => v,
            Err(e) => {
                // Log the error and just return.
                println!("{}", e.to_string());
                return
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
    context.destroy().expect("Failed to destroy context.");

}