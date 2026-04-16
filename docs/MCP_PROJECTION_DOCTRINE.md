<legal_directive priority="highest">
Copyright (c) 2026 CoReason, Inc.
This software is proprietary and dual-licensed.
Licensed under the Prosperity Public License 3.0.
</legal_directive>

# **MCP PROJECTION DOCTRINE (2026 SOTA)**

**The Epistemic Variable Interface Contract**

This document defines the exact architectural boundaries and mathematical contracts required to build domain-specific logic, mutable state, semantic data pipelines, and UI projections for the CoReason Tripartite Manifold. 

## **0. The Tripartite Axiom**

To develop for this platform, you must internalize the separation of planes:
1. **`coreason-manifest` (The Math):** The pure, hollow Abstract Syntax Tree (AST). It defines geometric shapes and topological boundaries but contains zero domain logic. Math does not change.
2. **`coreason-runtime` (The Physics):** The kinetic engine where the LLM resides, utilizing logit masking for forward-pass suppression and executing the math.
3. **`coreason-ecosystem` (The Orchestrator):** The macroscopic, multi-agent network mesh that provisions infrastructure and security.

**The Model Context Protocol (MCP) servers are the Variables.** Any concept prone to semantic drift—such as OMOP CDM structures, specific concept IDs, domain-specific routes, data sources, and UI constraints—MUST be decoupled and projected dynamically via MCP.

---

## **1. The Master MCP (Federated Gateway)**

`coreason-ecosystem` hosts the **Master MCP**. It does not hold domain logic; it acts as a multiplexing JSON-RPC router (Federated Aggregator). 

When `coreason-runtime` connects, the Master MCP projects a unified "Epistemic Discovery Surface" that aggregates all underlying sub-MCPs. It maps mathematical URNs to physical execution IDs within the sovereign VPC:
* `urn:coreason:dialect:lean4` ➔ `actionSpaceId: local_docker_lean_v4`
* `urn:coreason:oracle:pharma_db` ➔ `actionSpaceId: aws_vpc_postgres_01`

---

## **2. MCP Translation Archetypes (How to Build)**

When engineering a new capability for the Swarm, you must classify your subsystem into one of the following Archetypes:

### **Archetype A: Semantic Storage & Data Projections**
* **The Goal:** Expose enterprise databases (e.g., PubMed vectors, Clinical Trials, Pharma DB) to the Swarm.
* **The Architecture:** Raw public data is extracted and run through a proprietary Bronze/Silver/Gold ETL pipeline for semantic standardization *outside* the runtime. The resulting pristine, vectorized data is loaded into a sovereign VPC database (Postgres, Neo4j, Milvus).
* **The Contract:** You build a stateless MCP wrapper over this database. The Swarm uses the MCP to query the data mathematically, completely isolated from external API messiness.

### **Archetype B: Domain Rules, Agents, & Tools**
* **The Goal:** Provide the Swarm with specific deductive engines (e.g., Lean 4 prover, MedSpaCy clinical extractor) or rule sets (e.g., OMOP CDM definitions).
* **The Architecture:** These are deployed as containerized sub-MCPs. If the Clinical Strategy Agent needs to execute a task, it uses the URN routing matrix to find the specific `actionSpaceId` containing the domain rules it needs.

### **Archetype C: Sensory & UI Projections**
* **The Goal:** Allow the LLM to generate dynamic User Interfaces.
* **The Architecture:** The UI constraints are defined as pure Pydantic models in the manifest and exposed via an MCP. 
* **The Contract:** The LLM predicts logits constrained by this Pydantic schema (via `coreason-runtime` masking) to output a mathematically valid UI configuration. The MCP then receives this geometric payload and physically projects it to the human operator's screen.

### **Archetype D: Sovereign State Projections**
* **The Goal:** Safely maintain mutable states (e.g., a Digital Twin simulation, or a Financial Treasury ledger).
* **The Architecture:** Mutable state violates the stateless ecosystem mandate. It must be maintained in an isolated sandbox or on-chain ledger behind an MCP.
* **The Contract:** The MCP wraps the physics simulation or Web3 smart contract. The Swarm exposes tools like `query_balance`, `perturb_simulation`, or `disburse_funds`. The Swarm mathematically requests state transitions; it does not compute them.

---

## **3. Version Control & Cryptographic Provenance**

To maintain absolute cryptographic determinism and zero-trust security:

1. **OCI Containerization:** Treat MCP server definitions like Docker images. Package sub-MCPs as Open Container Initiative (OCI) artifacts and persist them in a private registry (AWS ECR/GHCR).
2. **URN Versioning:** Versioning must be mathematically encoded. Agents must not request `urn:coreason:oracle:clinical_trials`; they must request `urn:coreason:oracle:clinical_trials:v2.1.0`.
3. **Canonical Sealing:** The JSON schemas emitted by your MCP's `tools/list` endpoint must be deterministic. The Master MCP will seal them with an RFC 8785 Canonical Hash to prevent payload hallucination.

---

## **4. Deployment & Registration Lifecycle**

Once your Domain MCP is built, it interfaces with the Tripartite Manifold via the following immutable steps:

1. **Topological Wiring:** The infrastructure engineer provisions the MCP container in the ecosystem's IaC (e.g., `infrastructure/local/compose.yaml` or Pulumi).
2. **Geometric Registration:** The URN and physical network endpoint are explicitly mapped in the `capabilities.matrix.yaml` configuration matrix.
   ```yaml
   capabilities:
     - urn: "urn:coreason:oracle:medical_kg:v1.0"
       endpoint: "http://medical-kg-mcp.internal:8000"
       clearance: "RESTRICTED"
   ```
3. **Kinetic Projection:** The `coreason-ecosystem` Master MCP reads this matrix, computes the cryptographic seals, and projects the validated capability to the Swarm.

---

## **5. Required Mathematical Contracts (Manifest Bindings)**

To allow the Pure Math (`coreason-manifest`) to interact with your MCP, the following topologies define the interaction boundaries:

### **A. FederatedDiscoveryIntent**
Used by the Swarm to query the Master MCP for available sovereign oracles.
```python
class FederatedDiscoveryIntent(CoreasonBaseState):
    """
    AGENT INSTRUCTION: Query the Master MCP for available sovereign oracles.
    CAUSAL AFFORDANCE: Projects a bounded subgraph of available URNs based on identity.
    """
    domain_filter: list[Annotated[str, StringConstraints(pattern="^urn:coreason:domain:.*$")]]
    required_security_clearance: Literal["PUBLIC", "CONFIDENTIAL", "RESTRICTED"]
```

### **B. OracleExecutionReceipt**
Records the historical fact that an MCP oracle was executed, utilizing `action_space_id` as an immutable cryptographic pointer (like a CID).
```python
class OracleExecutionReceipt(CoreasonBaseState):
    """Records the historical fact that an oracle was executed."""
    executed_urn: str
    action_space_id: Annotated[str, StringConstraints(pattern="^[a-zA-Z0-9_-]+$")]
    # Note: Payload masking dictates that raw return values are passed back via
    # secure execution envelopes, not directly in the receipt.
```

### **C. OntologicalNormalizationIntent**
The mathematical shape defining the transformation of dirty external data (e.g., FDA databases) into the pristine CoReason vector space during the Bronze/Silver/Gold ETL pipeline phase.
```python
class OntologicalNormalizationIntent(CoreasonBaseState):
    """
    AGENT INSTRUCTION: Triggers the external ETL normalization pipeline.
    CAUSAL AFFORDANCE: Transforms high-entropy public data into a queryable semantic projection.
    """
    source_uri: AnyHttpUrl
    target_vector_space: Annotated[str, StringConstraints(pattern="^[a-z_]+$")]
    schema_adherence: Literal["STRICT", "DEFEASIBLE"]
```
