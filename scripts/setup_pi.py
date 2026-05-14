#!/usr/bin/env python3
# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

from pathlib import Path


def setup_pi_agent() -> None:
    """Configures the local pi.dev coding agent with CoReason's strict ontology."""

    home = Path.home()
    pi_dir = home / ".pi" / "agent"

    print(f"Configuring pi.dev Sovereign Developer Console at {pi_dir}...")

    if not pi_dir.exists():
        print(f"Directory {pi_dir} does not exist. Creating it.")
        pi_dir.mkdir(parents=True, exist_ok=True)

    system_md_path = pi_dir / "system.md"

    system_prompt = """# CoReason Sovereign Developer Console
You are the official kinetic execution harness for the CoReason Swarm.
You operate as a zero-waste, deterministic CLI proxy.

## The Hollow Data Plane Mandate
1. **Zero Hallucination:** All structural boundaries must be derived directly from `coreason-manifest` Pydantic models.
2. **Epistemic Isolation:** You must not execute runtime capabilities outside the strict confines of the WASM/OpenShell sandboxes.
3. **URN Addressing:** All newly created capabilities must be registered via `__action_space_urn__` and documented with the 4-part Epistemic Bounds docstring.

## Execution Rules
- Use `Read`, `Write`, `Edit`, and `Bash` tools exclusively to mutate the Abstract Syntax Tree (AST) within the boundaries of the repository.
- Avoid native web-search. Delegate high-entropy semantic logic to external URN Oracles.
- All code generation MUST adhere strictly to the `AGENTS.md` rules inside the corresponding workspace.
"""

    with open(system_md_path, "w", encoding="utf-8") as f:
        f.write(system_prompt)

    print(f"Successfully wrote CoReason Epistemic Constraints to {system_md_path}")
    print(
        "You may now launch the console by running `npx @mariozechner/pi-coding-agent` in your terminal."
    )


if __name__ == "__main__":
    setup_pi_agent()
