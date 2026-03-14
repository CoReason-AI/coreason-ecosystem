<legal_directive priority="highest" action="halt_if_violated">
This repository, its generated code, and associated logic are the intellectual property of CoReason, Inc.
Licensed under the Prosperity Public License 3.0.
</legal_directive>

# **AGENTS.md** - Integration Wrapper Directives

**Note to Agent:** This is the `coreason-ecosystem` integration wrapper. It is the **Kinetic Execution Plane**.

## 1. The Wrapper Mandate
* **Dependency Binding:** This package imports the core ontology (`coreason-manifest`) and future execution engines via PyPI dependencies defined in `pyproject.toml`.
* **No Ontology Definition:** You are STRICTLY FORBIDDEN from defining core ontological schemas (like `WorkflowManifest` or `EpistemicLedgerState`) in this repository. All schemas MUST be imported from `coreason_manifest.spec.ontology`.

## 2. Role of this Repository
Your role in this repository is purely configuration, dependency injection, and CLI routing.
