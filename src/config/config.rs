use serde::Deserialize;

#[derive(Debug)]
#[derive(Deserialize)]
pub struct Config {
    pub title: String,
    pub plugins: Plugins,
}

#[derive(Debug)]
#[derive(Deserialize)]
pub struct Plugins {
    pub internal: Vec<String>,
    pub external: Vec<String>,
}

