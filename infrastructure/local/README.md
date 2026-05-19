# Local Infrastructure

This directory contains the `compose.yaml` to run the CoReason Ecosystem locally.

## OpenShell Gateway Integration

The OpenShell Gateway and Supervisor binaries **MUST** run on the host machine, not inside the `compose.yaml` mesh. OpenShell creates sandboxes dynamically by bind-mounting the `openshell-sandbox` binary, overwriting entrypoints, clearing CMD arrays, and injecting kernel capabilities (`SYS_ADMIN`, `NET_ADMIN`, etc.). This requires host-level access.

### Host-Level Installation Steps

1. **Install OpenShell CLI:**
   Download the OpenShell Gateway binaries natively to your host. For example, via `cargo` or native binary downloads from the NVIDIA OpenShell repository.
   ```bash
   cargo install --git https://github.com/NVIDIA/OpenShell openshell-cli
   ```

2. **Start the Gateway:**
   Start the OpenShell Gateway daemon on your host machine to listen for incoming sandbox requests from the CoReason runtime.
   ```bash
   openshell gateway start --port 8080
   ```

3. **Configure Runtime:**
   When running the CoReason ecosystem, the `coreason-runtime` will connect to `http://host.docker.internal:8080` (or your host's IP) to dynamically request NemoClaw sandbox creations, instead of treating NemoClaw as a static container.
