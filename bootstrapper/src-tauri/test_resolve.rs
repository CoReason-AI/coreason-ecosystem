use tauri::Manager;

fn test_fn(app: &tauri::AppHandle) {
    let _ = app.path().resolve("../../infrastructure/local/compose.yaml", tauri::path::BaseDirectory::Resource);
}

fn main() {}
