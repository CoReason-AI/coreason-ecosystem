use crate::schema::{SwarmBootstrapIntent, SwarmBootstrapReceipt};
use std::env;
use std::process::Command;

pub fn check_dependencies(_intent: SwarmBootstrapIntent) -> SwarmBootstrapReceipt {
    let os_type = env::consts::OS.to_string();

    let docker_available = Command::new("docker")
        .arg("--version")
        .output()
        .map(|out| out.status.success())
        .unwrap_or(false);

    let docker_compose_available = Command::new("docker")
        .arg("compose")
        .arg("version")
        .output()
        .map(|out| out.status.success())
        .unwrap_or(false);
        
    // For NemoClaw, we assume it's part of the standard coreason CLI tools or path if installed locally.
    // If not, it will be pulled via docker compose, but the Bootstrapper might check for the binary if it runs natively.
    // Since we deploy it via Docker Compose in this configuration, it is available if Docker Compose is available.
    let nemoclaw_available = docker_compose_available;

    let status = if docker_available && docker_compose_available {
        "SUCCESS".to_string()
    } else {
        "FAILURE".to_string()
    };

    let message = if status == "SUCCESS" {
        "All base dependencies met. Ready to ignite swarm.".to_string()
    } else {
        "Missing Docker or Docker Compose. Please install Docker Desktop.".to_string()
    };

    SwarmBootstrapReceipt {
        status,
        message,
        os_type,
        docker_available,
        docker_compose_available,
        nemoclaw_available,
    }
}

use crate::schema::{SwarmIgnitionIntent, SwarmIgnitionReceipt};
use tauri::{Manager, Emitter};
use std::time::Duration;
use std::thread;
use std::process::Stdio;
use std::io::{BufRead, BufReader};

pub fn ignite_swarm(app: tauri::AppHandle, intent: SwarmIgnitionIntent) -> SwarmIgnitionReceipt {
    // 1. Resolve the path to the bundled compose.yaml
    // In Tauri v2, we get the resource_dir and join the path.
    let resource_dir = app.path().resource_dir();
    
    let compose_file_path = match resource_dir {
        Ok(mut path) => {
            // Note: Tauri replaces `../` with `_up_/` when bundling resources.
            path.push("_up_/_up_/infrastructure/local/compose.yaml");
            path
        },
        Err(_) => {
            return SwarmIgnitionReceipt {
                status: "FAILURE".to_string(),
                message: "Could not locate application resource directory.".to_string(),
            };
        }
    };

    let compose_path_str = compose_file_path.to_string_lossy().to_string();

    // 2. Execute docker compose up -d
    let mut command = Command::new("docker");
    command.arg("compose").arg("-f").arg(&compose_path_str);
    
    if intent.force_rebuild {
        command.arg("up").arg("--build").arg("-d");
    } else {
        command.arg("up").arg("-d");
    }

    // Pass required environment variables to prevent warnings and satisfy container requirements
    command.env("EPISTEMIC_MERKLE_ROOT", "0x0000000000000000000000000000000000000000000000000000000000000000");
    command.env("COREASON_TREASURY_CONTRACT", "0x0000000000000000000000000000000000000000");

    command.stdout(Stdio::piped());
    command.stderr(Stdio::piped());

    let mut child = match command.spawn() {
        Ok(c) => c,
        Err(e) => {
            return SwarmIgnitionReceipt {
                status: "FAILURE".to_string(),
                message: format!("Failed to spawn docker: {}", e),
            };
        }
    };

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let app_clone1 = app.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(l) = line {
                let _ = app_clone1.emit("boot-log", l);
            }
        }
    });

    let app_clone2 = app.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(l) = line {
                let _ = app_clone2.emit("boot-log", l);
            }
        }
    });

    let status = match child.wait() {
        Ok(s) => s,
        Err(e) => {
            return SwarmIgnitionReceipt {
                status: "FAILURE".to_string(),
                message: format!("Failed to wait on docker process: {}", e),
            };
        }
    };

    if !status.success() {
        return SwarmIgnitionReceipt {
            status: "FAILURE".to_string(),
            message: "Docker Compose failed to start containers.".to_string(),
        };
    }

    // 3. Health check loop (simulated check of MCP endpoint for now, or just return success)
    // In a real scenario we might poll http://localhost:8080/health using reqwest.
    // For this prototype, we'll sleep a bit to let containers spin up.
    thread::sleep(Duration::from_secs(3));

    SwarmIgnitionReceipt {
        status: "SUCCESS".to_string(),
        message: "Swarm ignited successfully. Sensory Command Center is coming online.".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_platform_detection_does_not_panic() {
        let intent = SwarmBootstrapIntent {
            environment_mode: "local".to_string(),
            include_default_kit: true,
        };
        let receipt = check_dependencies(intent);
        assert!(!receipt.os_type.is_empty());
    }
}
