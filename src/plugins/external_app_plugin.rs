use uuid::Uuid;
use crate::config::config::ExtPluginConfig;
use crate::{events, events::MonitorType, config::errors::Errors};
use event_engine::{plugins::ExternalPlugin};
use event_engine::errors::EngineError;
use event_engine::events::EventType;

use log::{error};

pub struct ExternalAppPlugin {
    plugin_name: String,
    id: Uuid,
    external_port: u16,
    subscriptions: Vec<String>,
}   

impl ExternalPlugin for ExternalAppPlugin {
    fn get_tcp_port(&self) -> i32 {self.external_port as i32}

    /// Returns the unique id for this plugin
    fn get_id(&self) -> Uuid {self.id}

    /// Returns the name for the plugin
    fn get_name(&self) -> String {self.plugin_name.clone()}

    /// Return the event subscriptions that this plugin is interested in.
    /// It's expected that this method will only be called once so that
    /// populating the vector on the fly does not introduce extra overhead.
    /// If this assumption does not hold, we should cache the populated vector.
    fn get_subscriptions(&self) -> Result<Vec<Box<dyn EventType>>, EngineError> {
        // Create the result vector.
        let mut event_types: Vec<Box<dyn EventType>> = vec![];

        // Populate the vector each
        for event_name in &self.subscriptions {
            match event_name.as_str() {
                "NewImageEvent" => {
                    event_types.push(Box::new(events::NewImageEvent::new(Uuid::new_v4(), String::from("fake"), vec![])),);
                },
                "ImageReceivedEvent" => {
                    event_types.push(Box::new(events::ImageReceivedEvent::new(Uuid::new_v4(), String::from("fake"))));
                },
                "ImageScoredEvent" => {
                    event_types.push(Box::new(events::ImageScoredEvent::new(Uuid::new_v4(), String::from("fake"), vec![])));
                },
                "ImageStoredEvent" => {
                    event_types.push(Box::new(events::ImageStoredEvent::new(Uuid::new_v4(), String::from("fake"), String::from("path"))));
                },
                "ImageDeletedEvent" => {
                    event_types.push(Box::new(events::ImageDeletedEvent::new(Uuid::new_v4(), String::from("fake"))));
                },
                "PluginTerminateEvent" => {
                    event_types.push(Box::new(events::PluginTerminateEvent::new(Uuid::new_v4(), String::from("*"))));
                },
                "PluginStartedEvent" => {
                    event_types.push(Box::new(events::PluginStartedEvent::new(Uuid::new_v4(), String::from("ObserverPlugin"))));
                },
                "PluginTerminatingEvent" => {
                    event_types.push(Box::new(events::PluginTerminatingEvent::new(Uuid::new_v4(), String::from("ObserverPlugin"))));
                },
                "MonitorPowerStartEvent" => {
                    event_types.push(Box::new(events::MonitorPowerStartEvent::new(vec!(1), vec!(MonitorType::ALL), String::from("2023-01-01T00:00:01.000000001+00:00"), 100)));
                },
                "MonitorPowerStopEvent" => {
                    event_types.push(Box::new(events::MonitorPowerStopEvent::new(vec!(1))));
                },
                other => {
                    let msg = format!("{}", Errors::EventNotHandledError(self.plugin_name.clone(), String::from(other)));
                    error!("{}", msg);
                    return Result::Err(EngineError::PluginExecutionError(self.plugin_name.clone(), self.id.to_string(), msg));
                },
            };
        }

        // We're good.
        Result::Ok(event_types)
    }
}

/// Associated functions.
impl ExternalAppPlugin {
    /// Allow access to the subscribed event names by cloning.
    #[allow(dead_code)]
    pub fn get_subscription_event_names(&self) -> Vec<String> {
        self.subscriptions.clone()
    }

    /// Create an external plugin from an external plugin configuration.
    /// If the need arises, we could provide the application's parameters
    /// here to customize external plugin configuration. This method
    /// consumes the incoming configuration argument.
    pub fn new(ext_config: &ExtPluginConfig) -> Result<Self, Errors> {
        // Make sure the terminate event is listed.
        if !ext_config.subscriptions.contains(&String::from("PluginTerminateEvent")) {
            let err = Errors::PluginMissingSubscription(ext_config.plugin_name.clone(), ext_config.id.clone());
            error!("{}", err);
            return Result::Err(err); 
        }

        // Convert the uuid's string represention into an object. 
        let uuid = match Uuid::parse_str(ext_config.id.as_str()) {
            Ok(u) => u,
            Err(e) => {return Result::Err(Errors::UUIDParseError(String::from("ext_config.id"), e.to_string()))},
        };

        // Create the camera app's external plugin.
        let app_plugin = ExternalAppPlugin {
            plugin_name: ext_config.plugin_name.clone(),
            id: uuid,
            external_port: ext_config.external_port,
            subscriptions: ext_config.subscriptions.clone(),
        };

        // We're good.
        Ok(app_plugin)
    }
}
