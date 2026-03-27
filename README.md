# 🌐 coreason-ecosystem

> **The Enterprise Control Plane & Macro-Orchestrator for the CoReason Swarm**

[![License: Prosperity 3.0](https://img.shields.io/badge/License-Prosperity_3.0-blue.svg)](https://prosperitylicense.com/versions/3.0.0)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![SOTA: 2026](https://img.shields.io/badge/Architecture-OEP_Manifold-purple.svg)]()

In Cognitive Systems Engineering, autonomous Swarms require absolute mathematical and physical boundaries. `coreason-ecosystem` is the **Autonomous Nervous System** (Governance Layer) of the Tripartite Cybernetic Manifold.

While the Swarm reasons internally, this package operates strictly on the exterior. It provides the declarative tools to deploy, distribute, document, and monitor the Swarm at an enterprise scale.

---

## 🏛️ The Tripartite Cybernetic Manifold (OEP)

To understand this package, you must understand its place in the CoReason architecture:

1. **[ Ontology ] `coreason-manifest`:** The Epistemic Boundary (JSON Schemas & AST).
2. **[ Execution ] `coreason-runtime`:** The Thermodynamic Engine (Extism WASM Sandbox).
3. **[ Projection ] `coreason-vscode`:** The Sensory Markov Blanket (Visual IDE).
4. **👉 [ Governance ] `coreason-ecosystem`:** The Macro-Orchestrator (This Repository).

---

## ⚙️ The Four Pillars of Orchestration

This CLI is divided into four strictly isolated cybernetic modules:

### I. The Infrastructure Bootstrapper (`deploy`)
Declarative management of the Swarm's physical infrastructure. Automatically provisions Temporal clusters, Redis pub/sub brokers, and scales `coreason-runtime` replicas across virtualized topologies. Enforces **Cryptographic Environment Sealing** to prevent daemons from booting with mismatched ontologies.

### II. The Epistemic Supply Chain (`registry`)
Treats WebAssembly (`.wasm`) capabilities as untrusted physical matter until mathematically verified. Handles compilation, extracts AST memory bounds, signs binaries with SHA-256 hashes, and distributes them to the runtime daemons.

### III. Zero-Waste Documentation (`docs`)
Human-written documentation is an epistemic hallucination. This module dynamically parses `coreason_ontology.schema.json` and WASM registry manifests to compile live, mathematically accurate Enterprise Developer Portals (MkDocs-Material).

### IV. Fleet Telemetry Aggregation (`monitor`)
Provides macro-observability. Taps into the aggregated Server-Sent Events (SSE) mesh to generate real-time terminal dashboards. Visualizes global Swarm entropy (latency and memory footprints) and suspended Oracle workflows.

---

## 🚀 Quickstart

`coreason-ecosystem` is built on modern Python 3.14+ and utilizes `uv` for hyper-fast dependency resolution.

```bash
# Clone the repository
git clone [https://github.com/CoReason-AI/coreason-ecosystem.git](https://github.com/CoReason-AI/coreason-ecosystem.git)
cd coreason-ecosystem

# Sync dependencies and build the virtual environment
uv sync

# Verify the Typer CLI router
uv run coreason-ecosystem --help
```

---

## 💻 CLI Topography

The human Topologist interfaces with the Swarm via the following command tree:

### Pillar I: Infrastructure
```bash
uv run coreason-ecosystem deploy up --env production
uv run coreason-ecosystem deploy status
uv run coreason-ecosystem deploy halt
```

### Pillar II: Registry
```bash
uv run coreason-ecosystem registry build ./capabilities/search_v2
uv run coreason-ecosystem registry push mcp_search_v2.wasm
```

### Pillar III: Documentation
```bash
uv run coreason-ecosystem docs build --strict
uv run coreason-ecosystem docs serve
```

### Pillar IV: Telemetry
```bash
uv run coreason-ecosystem monitor dashboard
uv run coreason-ecosystem monitor trace <workflow-id>
```

---

## 🛑 Agentic Directives

If you are an AI reasoning agent operating within this repository, you must immediately read and internalize `AGENTS.md`.

**The Principle of Non-Interference:** You are operating in the Macro-Orchestration boundary. You are strictly forbidden from modifying Pydantic models (`coreason-manifest`) or workflow execution logic (`coreason-runtime`). Your domain is Docker, Typer CLI routing, SSE aggregation, and MkDocs static generation.

---

## ⚖️ License

Copyright (c) 2026 CoReason, Inc.

This software is proprietary and dual-licensed.
Licensed under the **Prosperity Public License 3.0** (the "License").
A copy of the license is available at [https://prosperitylicense.com/versions/3.0.0](https://prosperitylicense.com/versions/3.0.0).

Commercial use beyond a 30-day trial requires a separate commercial license. For details, see the `LICENSE` file.
