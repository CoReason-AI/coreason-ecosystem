#cloud-config
#
# Deterministic cloud-init template for CoReason fleet node provisioning.
# Parameters are injected by the MeshInjector at rendering time:
#   - {{MESH_AUTH_KEY}}: Tailscale authentication key
#   - {{TEMPORAL_MESH_IP}}: Temporal cluster IP address
#   - {{WASM_MAX_PAGES}}: Maximum WASM memory pages
#   - {{FIREWALL_RULES}}: Rendered iptables commands (if network_isolation=True)
#
runcmd:
  - curl -fsSL https://tailscale.com/install.sh | sh
  - tailscale up --authkey={{MESH_AUTH_KEY}} --ssh
{{FIREWALL_RULES}}
  - curl -fsSL https://get.docker.com | sh
  - systemctl enable --now docker
  - docker run -d --net=host -e TEMPORAL_HOST={{TEMPORAL_MESH_IP}} -e WASM_MAX_PAGES={{WASM_MAX_PAGES}} -e MASTER_MCP_URI=http://coreason-master-gateway:8000/sse ghcr.io/coreason/coreason-runtime:latest
