use serde::Deserialize;


#[derive(Debug, Deserialize)]
pub struct Config {
    pub title: String,
    pub plugins: Plugins,
    pub publish_port: u16,
    pub subscribe_port: u16,
}

impl Config {
    fn new() -> Self {
        Config::default()
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            title: Default::default(),
            plugins: Default::default(),
            publish_port: 5559,
            subscribe_port: 5560,
        }
    }
}

#[derive(Debug, Deserialize, Default)]
pub struct Plugins {
    pub internal: Vec<String>,
    pub external: Vec<ExtPluginConfig>,
    pub run_gen_driver: Option<bool>,
}

#[derive(Debug, Deserialize, Default)]
pub struct ExtPluginConfig {
    pub plugin_name: String,
    pub id: String,
    pub external_port: u16,
    pub subscriptions: Vec<String>,
}

#[cfg(test)]
mod tests {
    use crate::config::config::Config;

    #[test]
    fn here_i_am() {
        println!("file test: main.rs");
    }

    #[test]
    fn print_config() {
        println!("{:?}", Config::new());
    }
}

