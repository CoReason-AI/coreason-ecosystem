# The Visual Cortex & Oracle Loop (Operate)

In legacy AI architectures, human operators interacted with autonomous agents via natural language chat windows. If an agent made a mistake, the operator would type, *"No, the correct patient ID is actually 12345."* This conversational feedback loop is mathematically flawed. It forces the AI to retroactively parse natural language and attempt to patch its own execution context, resulting in a 60% degradation in reasoning stability (known as *Reasoning Leakage*).

The CoReason paradigm completely abandons conversational interfaces. Instead, we utilize the **Human Oracle Circuit**—a deterministic, high-latency conduit between the Swarm's halted memory state and the operator's visual field.

This guide explains how human operators use the `coreason-vscode` extension to visually monitor the Swarm and deterministically inject truth into failing workflows.

## 1. Sensory Binding (The IDE Mesh)

The Swarm does not possess a native user interface. Instead, the `coreason-ecosystem` utilizes your Integrated Development Environment (VS Code) as its **Sensory Cortex**.

When you scaffolded your workspace (`coreason init`), the hypervisor generated a strict `.vscode/settings.json` file. This configuration physically binds the IDE to the Redis Server-Sent Events (SSE) mesh provisioned by `coreason up`.

**The Result:** Your code editor is now a live telemetry dashboard. As the background WASM daemon executes capabilities, you will see real-time execution nodes rendering natively in your VS Code panel.

## 2. The Epistemic Yield (When the Swarm Halts)

Standard AI agents are prone to thermodynamic runaway—if they encounter a highly obfuscated document they cannot parse, they will guess, hallucinate data, and crash the downstream database.

The `coreason-runtime` daemon prevents this by continuously calculating the agent's **Expected Free Energy** (Internal Uncertainty).

If the agent calculates that its uncertainty regarding a specific Pydantic schema exceeds the safety threshold ($\Gamma_{yield}$), it triggers an **Autonomic Halt**.

### The Visual Indicators:
1. **The WASM Suspension:** The background Extism WebAssembly thread physically pauses. It does not crash; its memory lattice is cryptographically frozen and held in state by the Temporal orchestrator.
2. **The Red Node:** An interrupt signal traverses the SSE mesh to your IDE. The specific execution node in your VS Code panel will flash **Red**, indicating an **Epistemic Yield**.

The agent is effectively stating: *"My calculus proves that guessing this data shape is too dangerous. I am yielding execution to the Human Oracle."*

## 3. The Human Oracle Circuit (Truth Injection)

When an Epistemic Yield occurs, you (the domain expert) must resolve the uncertainty.

1. **The Generative UI:** Click on the red halted node in VS Code. The extension will render a deterministic, native HTML input form that *exactly matches* the missing `coreason-manifest` JSON schema the agent failed to resolve.
2. **Ground-Truth Input:** You review the agent's context and manually type the correct, validated data into the form fields.
3. **One-Way Truth Injection:** When you click "Submit", the system does not "chat" with the AI. Instead, the Temporal orchestration engine executes a violent, **One-Way State Overwrite**.
    * It penetrates the suspended WASM agent's memory lattice.
    * It overwrites the hallucinated or missing intent.
    * It directly injects your exact JSON payload into the execution context as an absolute mathematical fact.

### Seamless Resumption
Once the injection is verified, the Extism sandbox thread is unpaused. The agent awakens, registers the injected payload as mathematically verified, and seamlessly resumes its orchestration pipeline without wasting a single cycle of redundant compute.

!!! success "Mathematical Guarantee"
    Because the Oracle Circuit bypasses the LLM's language parser entirely, the system mathematically guarantees 100% adherence to the human operator's payload. The Swarm cannot misinterpret a direct memory injection.
