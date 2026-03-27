# Capability Crystallization (Build)

In the CoReason paradigm, an AI agent is fundamentally treated as an untrusted, high-entropy prediction engine. Therefore, an agent is **never** permitted to write or execute raw Python code dynamically.

Tools must be explicitly defined by human domain experts and mathematically sealed into WebAssembly (WASM) before the agent is ever activated. We define this physical transformation from human-readable code to a mathematically bounded binary as **Capability Crystallization**.

This guide covers how Reasoning Engineers must write capabilities, and how the `coreason-ecosystem` compiler enforces the Epistemic Seal.

## 1. Writing Bounded Capabilities

A capability is a standard Python function, but its input and output boundaries are strictly governed by the universal topological contracts defined in `coreason-manifest`.

You cannot pass arbitrary strings or `**kwargs` into a CoReason capability. Every input and output must be a strictly verified Pydantic model.

### 1.1 The Anatomy of a Capability

Here is a SOTA example of an ETL capability designed to extract medical codes. Notice how the logic is sandwiched between strict, cryptographic data types.

```python
from coreason_manifest.spec.ontology import TransmutationIntent, ExecutionNodeReceipt
from pydantic import validate_call

@validate_call(validate_return=True)
def extract_snomed_codes(intent: TransmutationIntent) -> ExecutionNodeReceipt:
    """
    Extracts SNOMED CT codes from a raw medical text payload.
    """
    # 1. The intent.payload is guaranteed to match the exact schema
    source_data = intent.payload.raw_text

    # 2. Execute deterministic extraction logic...
    extracted_codes = ["12345", "67890"]

    # 3. Return a cryptographically frozen receipt (Append-Only)
    return ExecutionNodeReceipt(
        status="SUCCESS",
        artifacts_produced=extracted_codes
    )
```

!!! warning "The Anti-CRUD Mandate"
    Notice the use of `TransmutationIntent` rather than a generic "Update" payload. The `coreason-ecosystem` compiler will violently reject any Python capability that utilizes legacy CRUD terminology or circumvents the `@validate_call` Pydantic decorator. State transitions must be mapped as causal events.

## 2. The Epistemic Seal (`coreason build`)

Once your Python capabilities are authored in the `src/gold/` directory, they must be transformed into isolated physical matter. Raw `.py` files are not executed by the Swarm.

```bash
uv run coreason build ./src/gold/capabilities.py
```

### What Happens Under the Hood?

When you execute the build command, the hypervisor initiates a strict, 3-step physical sealing process:

1. **AOT Compilation:** The hypervisor invokes the SOTA WASM toolchain (`componentize-py`). It performs Ahead-Of-Time (AOT) compilation, translating your Python logic into a highly secure, memory-bounded `.wasm` binary. All host-system access (file system, arbitrary networking) is stripped during this compilation unless explicitly granted.
2. **Cryptographic Provenance:** The system calculates a unique SHA-256 hash of the resulting compiled `.wasm` binary (not the Python file). We define this hash as the **Epistemic Seal**.
3. **The Ledger Update:** This hash is written directly into `.coreason/capability_ledger.json`.

!!! success "Thread-Safe Builds"
    The `coreason build` command utilizes strict OS-level `FileLock` mechanisms when mutating the capability ledger. CI/CD pipelines can safely compile dozens of agent capabilities concurrently without risking a race condition or state corruption.

Once the seal is applied, the `coreason-runtime` engine will recalculate the hash of the WASM binary every single time an AI agent attempts to invoke it. If a developer, a bad actor, or an AI hallucination alters even a single byte of the compiled tool, the hashes will fail to match, and the execution will be instantly aborted.

## 3. Latent Memory & RAG Mounts

Because WebAssembly capabilities are executed in a zero-trust sandbox, they are fundamentally **stateless**. If your capability requires semantic memory (e.g., searching past execution receipts or querying a vector space), it cannot open a standard network socket to an external database.

To solve this, the ecosystem natively utilizes **LanceDB**.

Because LanceDB is an embedded database (running natively in-process rather than over a network boundary), the `coreason build` command seamlessly packages the LanceDB querying logic directly into the `.wasm` boundary.

This allows your isolated capability to perform lightning-fast Retrieval-Augmented Generation (RAG) and dense vector searches entirely within its own physical cage, without violating the Swarm's zero-trust network rules.
