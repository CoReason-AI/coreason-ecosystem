# ADR 0001: The Stateless Substrate & The Hollow Plane
**Date:** 2026-04-15
**Status:** ACCEPTED

## 1. Context
Legacy 2020s microservice orchestrators inherently bound themselves to the domain logic of the applications they deployed. API Gateways parsed specific REST paths, and deployment scripts hardcoded database schemas, medical vocabularies, and simulated physical states.

In a neurosymbolic swarm, this tight coupling creates catastrophic semantic drift. If the Governance Plane (`coreason-ecosystem`) is aware of the difference between "Clinical Trial Data" and "Financial Tick Data," it requires a physical code mutation every time the Swarm shifts its reasoning domain.

## 2. Decision
The Governance Plane is hereby mathematically severed from the Data and Compute planes. `coreason-ecosystem` is declared an **Invariant Substrate**.

1. **Eradication of Mutable State:** The ecosystem will maintain zero global mutable variables. The Treasury ledger and Digital Twin simulations are evicted to external, sovereign environments.
2. **Eradication of Domain Logic:** All hardcoded strings referencing domain reality (e.g., `Aspirin`, `g4dn.xlarge`) are formally banned.
3. **Stateless Variable Projection:** All domain-specific intelligence, external tools, and semantic data pipelines are reclassified as **Epistemic Variables**. They must be packaged as isolated containers and projected dynamically into the Swarm via the Model Context Protocol (MCP).

## 3. Consequences
* **Positive (Absolute Stability):** `coreason-ecosystem` is now immune to domain drift. The underlying Python architecture will not require a single line of code modification whether the Swarm is executing pharmaceutical research or weapon systems trajectory mapping.
* **Positive (Zero-Trust):** Because the ecosystem is structurally blind to the payloads passing through its MCP sockets, it treats all incoming data as hostile, enforcing pure RFC 8785 cryptographic isolation.
* **Constraint:** Developers are strictly forbidden from writing "custom API integrations" in the ecosystem. All external contact MUST be modeled as a Sovereign MCP Substrate.
