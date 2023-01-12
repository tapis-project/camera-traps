pub mod image_gen_plugin;
pub mod image_recv_plugin;
pub mod image_score_plugin;
pub mod image_store_plugin;
pub mod observer_plugin;
pub mod external_app_plugin;
pub mod actions;

#[cfg(test)]
mod tests {

    #[test]
    fn here_i_am() {
        println!("file test: plugins.rs");
    }
}
