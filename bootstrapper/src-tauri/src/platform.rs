use crate::schema::{
    NemoClawInstallReceipt, NemoClawOnboardIntent, NemoClawOnboardReceipt, SwarmBootstrapIntent,
    SwarmBootstrapReceipt, SwarmIgnitionIntent, SwarmIgnitionReceipt,
};
use std::env;
use std::io::{BufRead, BufReader};
use std::process::{Command, Stdio};
use std::thread;
use tauri::{Emitter, Manager};

// ─── Dependency Detection ────────────────────────────────────────────────────

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

    // Real binary check: does `~/.local/bin/nemoclaw` exist and is executable?
    let nemoclaw_installed = Command::new("sh")
        .arg("-c")
        .arg("[ -x ~/.local/bin/nemoclaw ]")
        .status()
        .map(|s| s.success())
        .unwrap_or(false);

    // Onboard check: `nemoclaw list` succeeds AND doesn't say "No sandboxes registered"
    // OR the openshell sandbox container is running.
    let nemoclaw_onboarded = if nemoclaw_installed {
        let list_success = Command::new("sh")
            .arg("-c")
            .arg("~/.local/bin/nemoclaw list")
            .output()
            .map(|out| {
                if out.status.success() {
                    let stdout = String::from_utf8_lossy(&out.stdout);
                    !stdout.contains("No sandboxes registered")
                } else {
                    false
                }
            })
            .unwrap_or(false);

        let docker_success = Command::new("sh")
            .arg("-c")
            .arg("docker ps -q --filter 'name=openshell' | grep -q .")
            .status()
            .map(|s| s.success())
            .unwrap_or(false);

        list_success || docker_success
    } else {
        false
    };

    // Determine the precise status code so the UI can route to the right step
    let status = if !docker_available || !docker_compose_available {
        "NEEDS_DOCKER".to_string()
    } else if !nemoclaw_installed {
        "NEEDS_NEMOCLAW_INSTALL".to_string()
    } else if !nemoclaw_onboarded {
        "NEEDS_NEMOCLAW_ONBOARD".to_string()
    } else {
        "SUCCESS".to_string()
    };

    let message = match status.as_str() {
        "NEEDS_DOCKER" => {
            "Missing Docker or Docker Compose. Please install Docker Desktop.".to_string()
        }
        "NEEDS_NEMOCLAW_INSTALL" => {
            "NemoClaw binary not found. The bootstrapper will install it automatically.".to_string()
        }
        "NEEDS_NEMOCLAW_ONBOARD" => {
            "NemoClaw is installed but not configured. Please provide your NGC API key to onboard."
                .to_string()
        }
        _ => "All dependencies satisfied. Ready to ignite swarm.".to_string(),
    };

    SwarmBootstrapReceipt {
        status,
        message,
        os_type,
        docker_available,
        docker_compose_available,
        nemoclaw_installed,
        nemoclaw_onboarded,
    }
}

// ─── NemoClaw Binary Installation ────────────────────────────────────────────

pub fn install_nemoclaw(app: tauri::AppHandle) -> NemoClawInstallReceipt {
    let _ = app.emit("boot-log", "[NemoClaw] Starting binary installation via NVIDIA installer...");

    // The official NVIDIA curl|bash installer for NemoClaw
    let mut child = match Command::new("sh")
        .arg("-c")
        .arg("curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash -s -- --non-interactive --yes-i-accept-third-party-software --fresh")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            return NemoClawInstallReceipt {
                status: "FAILURE".to_string(),
                message: format!("Failed to launch installer: {}", e),
            };
        }
    };

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let app_clone1 = app.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines().flatten() {
            let _ = app_clone1.emit("boot-log", format!("[NemoClaw Install] {}", line));
        }
    });

    let app_clone2 = app.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines().flatten() {
            let _ = app_clone2.emit("boot-log", format!("[NemoClaw Install] {}", line));
        }
    });

    let _ = child.wait();

    let check_child = Command::new("sh")
        .arg("-c")
        .arg("[ -x ~/.local/bin/nemoclaw ]")
        .status();

    if let Ok(status) = check_child {
        if status.success() {
            let _ = app.emit("boot-log", "[NemoClaw] ✅ Binary installed successfully.");
            return NemoClawInstallReceipt {
                status: "SUCCESS".to_string(),
                message: "NemoClaw binary installed. Please provide your NGC API key to onboard."
                    .to_string(),
            };
        }
    }

    NemoClawInstallReceipt {
        status: "FAILURE".to_string(),
        message: "Installer exited and ~/.local/bin/nemoclaw was not found. Please check your internet connection.".to_string(),
    }
}

// ─── NemoClaw Onboarding ─────────────────────────────────────────────────────

pub fn onboard_nemoclaw(app: tauri::AppHandle, intent: NemoClawOnboardIntent) -> NemoClawOnboardReceipt {
    let _ = app.emit(
        "boot-log",
        format!(
            "[NemoClaw] Starting non-interactive onboarding for sandbox '{}'...",
            intent.sandbox_name
        ),
    );

    // Run nemoclaw onboard in fully non-interactive mode.
    // NGC_API_KEY env var is consumed by the nemoclaw CLI for authentication.
    // --non-interactive --yes suppresses all prompts.
    // --yes-i-accept-third-party-software accepts the NVIDIA software notice.
    // --no-gpu avoids GPU detection blocking in CI/dev environments.
    let mut child = match Command::new("nemoclaw")
        .args([
            "onboard",
            "--non-interactive",
            "--yes",
            "--yes-i-accept-third-party-software",
            "--no-gpu",
            "--name",
            &intent.sandbox_name,
        ])
        .env("NGC_API_KEY", &intent.ngc_api_key)
        .env("NVIDIA_API_KEY", &intent.ngc_api_key)
        .env("NEMOCLAW_GATEWAY_PORT", "8088")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            return NemoClawOnboardReceipt {
                status: "FAILURE".to_string(),
                message: format!("Failed to launch nemoclaw onboard: {}", e),
            };
        }
    };

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let (tx, rx) = std::sync::mpsc::channel();
    let tx_out = tx.clone();
    let tx_err = tx;

    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines().flatten() {
            let _ = tx_out.send(line);
        }
    });

    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines().flatten() {
            let _ = tx_err.send(line);
        }
    });

    let mut success_detected = false;

    for line in rx {
        let _ = app.emit("boot-log", format!("[NemoClaw Onboard] {}", line));
        
        // The NemoClaw non-interactive onboard hangs indefinitely waiting for the dashboard.
        // We detect the success state and manually terminate the process.
        if line.contains("Waiting for NemoClaw dashboard") || line.contains("dashboard to become ready") {
            success_detected = true;
            let _ = child.kill();
            break;
        }
    }

    let _ = child.wait();

    if success_detected {
        let _ = app.emit("boot-log", "[NemoClaw] ✅ Onboarding complete. Sandbox is ready.");
        NemoClawOnboardReceipt {
            status: "SUCCESS".to_string(),
            message: format!(
                "NemoClaw sandbox '{}' onboarded successfully.",
                intent.sandbox_name
            ),
        }
    } else {
        NemoClawOnboardReceipt {
            status: "FAILURE".to_string(),
            message: "nemoclaw onboard exited with an error. Check the NGC API key and try again.".to_string(),
        }
    }
}

// ─── Hardware Detection ───────────────────────────────────────────────────────

fn has_nvidia_gpu() -> bool {
    // Attempt to run nvidia-smi. If it succeeds, the system likely has an active NVIDIA GPU.
    match Command::new("nvidia-smi").stdout(Stdio::null()).stderr(Stdio::null()).status() {
        Ok(status) => status.success(),
        Err(_) => false,
    }
}

// ─── Swarm Ignition ───────────────────────────────────────────────────────────

pub fn ignite_swarm(app: tauri::AppHandle, intent: SwarmIgnitionIntent) -> SwarmIgnitionReceipt {
    let resource_dir = app.path().resource_dir();

    let compose_file_path = match resource_dir {
        Ok(mut path) => {
            path.push("_up_/_up_/infrastructure/local/compose.yaml");
            path
        }
        Err(_) => {
            return SwarmIgnitionReceipt {
                status: "FAILURE".to_string(),
                message: "Could not locate application resource directory.".to_string(),
            };
        }
    };

    let compose_path_str = compose_file_path.to_string_lossy().to_string();

    // Automatically log into GHCR if the user provided credentials in the intent
    if let (Some(token), Some(user)) = (intent.github_pat, intent.github_user) {
        let _ = app.emit("boot-log", &format!("[Auth] Received GHCR credentials for user {}. Authenticating...", user));
        
        // Use docker login with --password-stdin
        use std::io::Write;
        let login_cmd = Command::new("docker")
            .arg("login")
            .arg("ghcr.io")
            .arg("-u")
            .arg(&user)
            .arg("--password-stdin")
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn();
            
        if let Ok(mut child) = login_cmd {
            if let Some(mut stdin) = child.stdin.take() {
                let _ = stdin.write_all(token.as_bytes());
            }
            let _ = child.wait();
            let _ = app.emit("boot-log", "[Auth] GHCR Authentication complete.");
        }
    }

    let mut command = Command::new("docker");
    command.arg("compose").arg("-f").arg(&compose_path_str);

    if intent.force_rebuild {
        command.arg("up").arg("--build").arg("-d");
    } else {
        command.arg("up").arg("-d");
    }

    command.env(
        "EPISTEMIC_MERKLE_ROOT",
        "0x0000000000000000000000000000000000000000000000000000000000000000",
    );
    command.env(
        "COREASON_TREASURY_CONTRACT",
        "0x0000000000000000000000000000000000000000",
    );

    let runtime_image = if has_nvidia_gpu() {
        let _ = app.emit("boot-log", "[Hardware] NVIDIA GPU Detected. Pulling coreason-runtime:latest-gpu (11GB)...");
        "ghcr.io/coreason-ai/coreason-runtime:20260515_docker_build_fix-gpu"
    } else {
        let _ = app.emit("boot-log", "[Hardware] No NVIDIA GPU Detected. Pulling coreason-runtime:latest-cpu (1.5GB)...");
        "ghcr.io/coreason-ai/coreason-runtime:20260515_docker_build_fix-cpu"
    };

    command.env("COREASON_RUNTIME_IMAGE", runtime_image);

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
        for line in reader.lines().flatten() {
            let _ = app_clone1.emit("boot-log", line);
        }
    });

    // We will buffer stderr to include it in the error message if something fails
    let (tx_err, rx_err) = std::sync::mpsc::channel();
    let app_clone2 = app.clone();
    
    thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines().flatten() {
            let _ = app_clone2.emit("boot-log", line.clone());
            let _ = tx_err.send(line);
        }
    });

    match child.wait() {
        Ok(s) if s.success() => SwarmIgnitionReceipt {
            status: "SUCCESS".to_string(),
            message: "Swarm ignited successfully. Sensory Command Center is coming online."
                .to_string(),
        },
        Ok(_) => {
            // Collect the captured stderr to show the exact docker compose error to the user
            let mut error_logs = String::new();
            for line in rx_err {
                error_logs.push_str(&line);
                error_logs.push('\n');
            }
            // Truncate if it's too long for the UI
            let display_err = if error_logs.is_empty() {
                "Unknown error.".to_string()
            } else if error_logs.len() > 500 {
                format!("{}...", &error_logs[error_logs.len() - 500..])
            } else {
                error_logs
            };

            SwarmIgnitionReceipt {
                status: "FAILURE".to_string(),
                message: format!("Docker Compose failed to start containers.\n\nLogs:\n{}", display_err),
            }
        },
        Err(e) => SwarmIgnitionReceipt {
            status: "FAILURE".to_string(),
            message: format!("Failed to wait on docker process: {}", e),
        },
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

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

pub fn uninstall_nemoclaw(app: tauri::AppHandle) -> Result<(), String> {
    let _ = app.emit("boot-log", "[Uninstall] Removing NemoClaw containers...");
    Command::new("sh")
        .arg("-c")
        .arg("docker rm -f $(docker ps -aq --filter 'name=coreason') 2>/dev/null")
        .status()
        .ok();
    
    Command::new("sh")
        .arg("-c")
        .arg("docker rm -f $(docker ps -aq --filter 'name=openshell') 2>/dev/null")
        .status()
        .ok();

    let _ = app.emit("boot-log", "[Uninstall] Removing NemoClaw CLI and config...");
    Command::new("sh")
        .arg("-c")
        .arg("rm -f ~/.local/bin/nemoclaw && rm -rf ~/.nemoclaw && rm -rf ~/.local/state/nemoclaw")
        .status()
        .ok();

    let _ = app.emit("boot-log", "[Uninstall] Complete. Environment reset.");
    Ok(())
}
