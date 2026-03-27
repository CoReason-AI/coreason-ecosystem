# The Lexical Architecture

When writing Python capabilities to be compiled into WASM by the `coreason-ecosystem`, developers are strictly bound to the Lexical Architecture defined by `coreason-manifest`.

## The Anti-CRUD Mandate
Legacy CRUD terminology flattens softmax distributions and introduces semantic drift.

* **BANNED TERMS:** `Create`, `Read`, `Update`, `Delete`, `Remove`, `Group`, `List`, `User`, `Data`, `Memory`, `Link`.
* **REQUIRED PARADIGM:** State transitions must be mapped using Judea Pearl’s Structural Causal Models (e.g., `Transmutation`, `DefeasibleCascade`, `StateMutationIntent`).

If a capability uses banned legacy terminology, the Epistemic Registry will reject the compilation.

## Categorical Suffixing (Topological Contracts)
Every schema injected into the runtime MUST terminate with an exact bounding suffix. These establish strict physical and temporal bounds on the object's execution:

- **`...Event` / `...Receipt`**: Cryptographically frozen historical facts (Append-only).
- **`...Intent` / `...Task`**: Authorized kinetic execution triggers.
- **`...Policy` / `...Contract` / `...SLA`**: Rigid mathematical boundaries governing global constraints (e.g., VRAM allocations).
- **`...State` / `...Snapshot` / `...Manifest` / `...Profile`**: Ephemeral or declarative N-dimensional coordinates.
