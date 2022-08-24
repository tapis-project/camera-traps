use serde::Deserialize;
use toml::value::Datetime;

#[derive(Deserialize)]
pub struct Config {
    pub title: String,
    pub owner: Owner,
}

#[derive(Deserialize)]
pub struct Owner {
    pub name: String,
    pub dob:  Datetime,
}

