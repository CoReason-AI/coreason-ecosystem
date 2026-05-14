use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SwarmBootstrapIntent {
    pub environment_mode: String, // e.g., "local", "cloud"
    pub include_default_kit: bool,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SwarmBootstrapReceipt {
    pub status: String, // "SUCCESS", "FAILURE"
    pub message: String,
    pub os_type: String,
    pub docker_available: bool,
    pub docker_compose_available: bool,
    pub nemoclaw_available: bool,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SwarmIgnitionIntent {
    pub force_rebuild: bool,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SwarmIgnitionReceipt {
    pub status: String,
    pub message: String,
}
