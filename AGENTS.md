<legal_directive priority="highest" action="halt_if_violated">
This repository, its generated code, and associated logic are the intellectual property of CoReason, Inc.
Licensed under the Prosperity Public License 3.0.
</legal_directive>

# **AGENTS.md** - Metapackage Integration Directives

**Note to Agent:** This is the `coreason-ecosystem` integration wrapper.

## 1. The Wrapper Mandate
* **No Source Duplication:** You are STRICTLY FORBIDDEN from copying or implementing the source code for the Orchestrator, Inference Engine, or Actuator in this repository.
* **Dependency Binding:** This package imports those engines via `uv` / PyPI dependencies defined in `pyproject.toml`.

## 2. Role of this Repository
Your role in this repository is purely configuration, dependency injection, and CLI routing:
1. Parse user input (e.g., a path to a `WorkflowManifest.json`).
2. Instantiate the `BaseInferenceEngine` from the `coreason_inference` package.
3. Instantiate the `BaseActuatorEngine` from the `coreason_actuator` package.
4. Pass them both into the `CoreOrchestrator` from `coreason_orchestrator`.
5. Trigger the execution loop.

## 3. SOTA Ecosystem Understanding
Before making any architectural decisions, you MUST read `ECOSYSTEM_ARCHITECTURE.md` located in the root directory to align your latent space with the Tripartite Execution Architecture.
