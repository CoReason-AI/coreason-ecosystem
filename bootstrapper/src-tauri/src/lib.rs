pub mod schema;
pub mod platform;

use crate::schema::{
    NemoClawInstallReceipt, NemoClawOnboardIntent, NemoClawOnboardReceipt,
    SwarmBootstrapIntent, SwarmBootstrapReceipt, SwarmIgnitionIntent, SwarmIgnitionReceipt,
};

#[tauri::command]
async fn check_dependencies(intent: SwarmBootstrapIntent) -> SwarmBootstrapReceipt {
    platform::check_dependencies(intent)
}

#[tauri::command]
async fn install_nemoclaw(app: tauri::AppHandle) -> NemoClawInstallReceipt {
    platform::install_nemoclaw(app)
}

#[tauri::command]
async fn onboard_nemoclaw(app: tauri::AppHandle, intent: NemoClawOnboardIntent) -> NemoClawOnboardReceipt {
    platform::onboard_nemoclaw(app, intent)
}

#[tauri::command]
async fn ignite_swarm(app: tauri::AppHandle, intent: SwarmIgnitionIntent) -> SwarmIgnitionReceipt {
    platform::ignite_swarm(app, intent)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            check_dependencies,
            install_nemoclaw,
            onboard_nemoclaw,
            ignite_swarm
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
