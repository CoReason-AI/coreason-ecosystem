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
    pub status: String, // "SUCCESS", "FAILURE", "NEEDS_NEMOCLAW_INSTALL", "NEEDS_NEMOCLAW_ONBOARD"
    pub message: String,
    pub os_type: String,
    pub docker_available: bool,
    pub docker_compose_available: bool,
    pub nemoclaw_installed: bool,   // true if the `nemoclaw` binary is on PATH
    pub nemoclaw_onboarded: bool,   // true if `nemoclaw list` returns at least one sandbox
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NemoClawInstallReceipt {
    pub status: String, // "SUCCESS", "FAILURE"
    pub message: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NemoClawOnboardIntent {
    pub ngc_api_key: String,
    pub sandbox_name: String, // e.g. "coreason"
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NemoClawOnboardReceipt {
    pub status: String, // "SUCCESS", "FAILURE"
    pub message: String,
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
