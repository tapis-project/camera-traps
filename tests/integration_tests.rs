
#[test]
fn hello() {
    println!("integration_tests.rc say hello!");
}

// fn run_test_driver(&self, pub_socket: &Socket) {

//         thread::sleep(time::Duration::new(3, 0));
//         info!("{}", "---------------- run_test_driver Waking UP!");// Create event.
//         let ev = events::ImageReceivedEvent::new(Uuid::new_v4());
//         let bytes = match ev.to_bytes() {
//             Ok(v) => v,
//             Err(e) => {
//                 // Log the error and just return.
//                 let msg = format!("{}", Errors::EventToBytesError(self.name.clone(), ev.get_name(), e.to_string()));
//                 error!("{}", msg);
//                 return
//             } 
//         };

//         // Send the event.
//         match pub_socket.send(bytes, 0) {
//             Ok(_) => (),
//             Err(e) => {
//                 // Log the error and abort if we can't send our start up message.
//                 let msg = format!("{}", Errors::SocketSendError(self.name.clone(), ev.get_name(), e.to_string()));
//                 error!("{}", msg);
//             }
//         };
// }