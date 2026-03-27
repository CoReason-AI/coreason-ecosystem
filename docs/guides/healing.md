# Maintenance & Autopoietic Healing (Maintain)

In long-running autonomous systems, software does not simply "break"; it experiences **Ontological Drift**.

Drift occurs when the rules of physical reality (defined in `coreason-manifest`) become desynchronized from the execution state (the compiled `.wasm` binaries) or the sensory UI (the IDE extensions). If left unchecked, this drift causes catastrophic database corruption.

The `coreason-ecosystem` is designed to be **autopoietic** (self-maintaining). It utilizes cryptographic proofs to detect drift and autonomic commands to heal itself. This guide provides SREs with the operational protocols to maintain the Swarm's mathematical integrity.

## 1. Detecting Ontological Drift

The Swarm relies on **Continuous State Attestation**. Every time the IDE or the orchestration engine attempts a state transition, the hypervisor checks the master Merkle tree: `.coreason/registry.lock`.

This cryptographic lock is a synthesized hash of three components:
1. The active version of the `coreason-manifest` schemas.
2. The active version of the `coreason-runtime` Docker daemon.
3. The individual SHA-256 hashes of every WASM capability in the ledger.

If a developer updates a Pydantic schema to require a new `email_address` field, but forgets to recompile the WASM tool, the Merkle tree breaks. The Swarm will violently reject all network requests, throwing an **Epistemic Mismatch** error to the IDE.

### 1.1 The Diagnostic Protocol (`coreason doctor`)

When the Swarm halts due to a mismatch, you do not need to manually hunt for the broken schema. Execute the diagnostic sweep:

```bash
uv run coreason doctor
```

**The Output:** The CLI will traverse the local state, query the active Docker daemon, and compare the hashes. It will render a deterministic Rich terminal table pinpointing the exact layer of the mismatch (e.g., *"Runtime daemon expects capability hash X, but local ledger reports hash Y"*).

## 2. The Healing Cascade (`coreason sync`)

Once an Epistemic Mismatch is diagnosed, the Swarm must be healed. You do not manually patch the components; you trigger the Autopoietic Healing Cascade.

```bash
uv run coreason sync
```

!!! success "The Autonomic Resolution"
    Executing `sync` forces the hypervisor to mathematically reconcile the environment:
    1. **Dependency Alignment:** It forces `uv` to pull the exact matching versions of the manifest and runtime.
    2. **Mass Re-Crystallization:** It iterates through `src/gold/`, recompiling all Python capabilities into fresh WASM binaries to match the updated schemas.
    3. **Ledger Regeneration:** It calculates the new cryptographic hashes, seals the `capability_ledger.json`, and computes a new `registry.lock`.
    4. **Hot-Swap:** It safely restarts the `coreason-runtime` daemon within the Docker mesh, injecting the new mathematical reality without dropping the PostgreSQL database connection.

## 3. Scaling to Bare-Metal (Proxmox & Pulumi)

While `coreason up` provisions a local Docker Compose mesh for development, enterprise Swarms require distributed, highly available physical hardware.

The `coreason-ecosystem` natively ships with Infrastructure-as-Code (IaC) templates to deploy the Swarm to bare-metal environments using **Pulumi** and **Proxmox**.

### 3.1 The Bare-Metal Architecture

Navigate to the `infrastructure/bare-metal/` directory.

```bash
cd infrastructure/bare-metal/
```

This directory contains the SOTA Python `__main__.py` Pulumi blueprint. When executed, this blueprint provisions:
* **Proxmox LXC Containers:** Dedicated, low-overhead Linux containers for the Temporal Orchestrator and the PostgreSQL Epistemic Ledger.
* **Proxmox VMs (QEMU):** Heavily isolated Virtual Machines equipped with strict `cgroups v2` boundaries to run the Extism WASM execution daemons.
* **Cryptographic Tunnels:** A WireGuard VPN mesh is automatically provisioned between the VMs, ensuring the Zero-Trust network topology is maintained across disparate physical nodes.

### 3.2 Executing the Deployment

Ensure your Pulumi CLI is authenticated and your `PULUMI_CONFIG_PASSPHRASE` is set, then execute the physical provisioner:

```bash
pulumi up
```

The hypervisor will output the exact WireGuard peer configurations and IP coordinates required to bind your local `coreason-vscode` IDE to the new, bare-metal Swarm cluster.
