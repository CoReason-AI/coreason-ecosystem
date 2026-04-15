# 1. Macro-Orchestrator Boundaries

Date: 2026-04-15

## Status

Accepted

## Context

The `coreason-ecosystem` repository manages the Governance Layer of the CoReason Tripartite Cybernetic Manifold. Our architecture fundamentally separates Governance, Execution, and Ontology across three primary repositories. We need to explicitly define and preserve the physical boundaries of this macro-orchestrator, avoiding overlap with swarm intelligence execution or fundamental data structure generation.

## Decision

We will intentionally maintain `coreason-ecosystem` as a physically separate Macro-Orchestrator, distinct from `coreason-runtime` (which handles execution) and `coreason-manifest` (which provides the underlying system ontology).

This repository's scope is strictly confined to:
* CLI routing and ecosystem management (`typer`)
* Infrastructure configuration and provisioning logic (e.g., Docker, Pulumi)
* System-Sent Events (SSE) telemetry aggregation
* Automated generation of epistemic documentation from bounded tools

## Consequences

* **Positive**: Strict separation of concerns increases modularity, security, and stability. Modifying execution context or ontological boundaries cannot inadvertently mutate governance tools.
* **Positive**: Enforces "The Principle of Non-Interference" - governance code cannot directly alter swarm logic.
* **Negative**: Increases the synchronization overhead required to match tyings and versions across the three repository ecosystem (`manifest`, `runtime`, and `ecosystem`). Cross-boundary modifications require carefully coordinated releases.
