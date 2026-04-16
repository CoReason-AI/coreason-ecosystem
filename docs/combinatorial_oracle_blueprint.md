<legal_directive priority="highest">
Copyright (c) 2026 CoReason, Inc.
This software is proprietary and dual-licensed.
Licensed under the Prosperity Public License 3.0.
</legal_directive>

# The Combinatorial Solver Oracle: A Sovereign MCP Blueprint
**Archetype B Reference Implementation â€” Domain Rules, Agents, & Tools**

This document is a textbook application of the **[MCP Projection Doctrine](MCP_PROJECTION_DOCTRINE.md)**.

By extracting the `CombinatorialSolverOracle` out of `coreason-manifest`, the Manifest is successfully purified into a **Hollow Data Plane**. The Manifest should only define the *geometric shape* of a `FormalLogicProofReceipt`; it should never load C-bindings (like `clingo`), spawn multiprocessing pipes, or manage physical timeouts.

As defined in the Doctrine, this extraction falls strictly under **Archetype B: Domain Rules & Tools**. It must be deployed as a stateless, containerized sub-MCP within the sovereign VPC. The Kinetic Plane (`coreason-runtime`) will call this tool, and the Governance Plane (`coreason-ecosystem`) will route it.

The following is the complete, production-ready blueprint to deploy the Combinatorial Oracle as a Sovereign MCP.

---

## 1. The MCP Server Implementation (`server.py`)

This code completely decouples `clingo` from the CoReason manifest. It receives a raw ASP program, executes it in an isolated multiprocessing sandbox to enforce the **Thermodynamic Guillotine** (timeouts), and returns a raw JSON payload. The Kinetic Plane will automatically cast this JSON back into the `FormalLogicProofReceipt` Pydantic model.

```python
# Copyright (c) 2026 CoReason, Inc
# Licensed under the Prosperity Public License 3.0
# Sovereign MCP: Combinatorial Solver Oracle

import json
import multiprocessing
import queue as pyqueue
import time
from typing import Any

import mcp.server
import mcp.types as types
from fastapi import FastAPI
from mcp.server.sse import SseServerTransport

import clingo
from clingo.ast import ASTType, Function, Literal, ProgramBuilder, Sign, SymbolicAtom, Transformer, parse_string
from clingo.control import Control

app = FastAPI(title="coreason-combinatorial-mcp")
mcp_server = mcp.server.Server("coreason-combinatorial-mcp")

class AssumptionTransformer(Transformer):
    def __init__(self, rule_map: dict[str, str]) -> None:
        self.rule_idx = 0
        self.rule_map = rule_map

    def visit_Rule(self, rule: clingo.ast.AST) -> clingo.ast.AST:
        idx = self.rule_idx
        self.rule_idx += 1
        assumption_name = f"__assume_{idx}"
        self.rule_map[assumption_name] = str(rule)

        loc = rule.location
        fun = Function(loc, assumption_name, [], 0)
        sym_atom = SymbolicAtom(fun)
        lit = Literal(loc, Sign.NoSign, sym_atom)

        new_body = [*list(rule.body), lit]
        return rule.update(body=new_body)

def _clingo_isolated_worker(asp_program: str, queue: multiprocessing.Queue) -> None:
    """Executes the ASP program in an isolated process to prevent C-binding deadlocks."""
    try:
        ctl = Control(["0"])
        parsed_rules = []

        def on_statement(stm: clingo.ast.AST) -> None:
            parsed_rules.append(stm)

        try:
            parse_string(asp_program, on_statement)
        except RuntimeError as e:
            queue.put({
                "satisfiability": "UNKNOWN",
                "answer_sets": [],
                "unsat_core": [str(e)[:2000]]
            })
            return

        rule_map: dict[str, str] = {}
        transformer = AssumptionTransformer(rule_map)

        with ProgramBuilder(ctl) as builder:
            for stm in parsed_rules:
                if stm.ast_type == ASTType.Rule:
                    new_stm = transformer(stm)
                    builder.add(new_stm)
                    parsed_choice: list[clingo.ast.AST] = []

                    def on_choice(s: clingo.ast.AST, pc: list[clingo.ast.AST] = parsed_choice) -> None:
                        pc.append(s)

                    parse_string(f"{{ __assume_{transformer.rule_idx - 1} }}.", on_choice)
                    for cstm in parsed_choice:
                        if cstm.ast_type == ASTType.Rule:
                            builder.add(cstm)
                else:
                    builder.add(stm)

        ctl.ground([("base", [])])
        models = []

        def on_model(m: clingo.Model) -> None:
            symbols = [str(sym) for sym in m.symbols(shown=True) if not sym.name.startswith("__assume_")]
            models.append(symbols)

        assumptions = [(clingo.Function(k), True) for k in rule_map]

        with ctl.solve(yield_=True, assumptions=assumptions, on_model=on_model) as handle:
            for _ in handle: pass
            result = handle.get()

            if result.satisfiable:
                queue.put({"satisfiability": "SATISFIABLE", "answer_sets": models, "unsat_core": []})
                return
            if result.unsatisfiable:
                core_symbols = handle.core()
                if len(core_symbols) > 0 and isinstance(core_symbols[0], int):
                    core_syms_mapped = []
                    for lit in core_symbols:
                        core_syms_mapped.extend(sa.symbol for sa in ctl.symbolic_atoms if sa.literal == lit)
                    core_symbols = core_syms_mapped

                unsat_core_strings = [rule_map[sym.name] for sym in core_symbols if sym.name in rule_map]
                queue.put({"satisfiability": "UNSATISFIABLE", "answer_sets": [], "unsat_core": [s[:2000] for s in unsat_core_strings]})
                return

    except RuntimeError as e:
        queue.put({"satisfiability": "UNKNOWN", "answer_sets": [], "unsat_core": [str(e)[:2000]]})
        return

    queue.put({"satisfiability": "UNKNOWN", "answer_sets": [], "unsat_core": []})

@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="evaluate_asp_program",
            description="Executes an Answer Set Programming (ASP) formal logic premise using clingo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "asp_program": {
                        "type": "string",
                        "description": "The exact ASP syntax to evaluate."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Maximum execution time before the thermodynamic guillotine is applied.",
                        "default": 10000
                    }
                },
                "required": ["asp_program"]
            },
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name != "evaluate_asp_program":
        raise ValueError(f"Unknown tool: {name}")

    asp_program = arguments["asp_program"]
    timeout_sec = arguments.get("timeout_ms", 10000) / 1000.0

    ctx = multiprocessing.get_context("spawn")
    mp_queue = ctx.Queue()

    process = ctx.Process(target=_clingo_isolated_worker, args=(asp_program, mp_queue))
    process.start()

    try:
        receipt_data = mp_queue.get(timeout=timeout_sec)
        process.join()
    except pyqueue.Empty:
        if process.is_alive():
            process.kill()
            process.join()

        receipt_data = {
            "satisfiability": "UNKNOWN",
            "answer_sets": [],
            "unsat_core": ["Execution terminated: Thermodynamic bound exceeded (SIGKILL applied)."]
        }

    return [types.TextContent(type="text", text=json.dumps(receipt_data))]

sse_transport = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse(request: Request):
    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)
```

---

## 2. OCI Containerization (`Dockerfile`)

Per **Rule 3: Version Control & Cryptographic Provenance** of the MCP Projection Doctrine, this logic must be packaged as an immutable artifact.

```dockerfile
FROM python:3.14-slim

WORKDIR /app

# System dependencies for clingo C-bindings
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Install specific Python requirements
RUN pip install --no-cache-dir mcp fastapi uvicorn clingo

COPY server.py .

# Expose the SSE port
EXPOSE 8000

# The orchestrator handles network isolation; the container just runs the server.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 3. Topological Egress (Wiring into `coreason-ecosystem`)

Once this container is built and pushed to your internal registry (e.g., `ghcr.io/coreason/mcp-combinatorial:v1.0.0`), you simply project it into the Swarm via the `coreason-ecosystem` Matrix Substrate without writing a single line of Python.

Update your `capabilities.matrix.yaml`:

```yaml
capabilities:
  - urn: "urn:coreason:oracle:combinatorial"
    endpoint: "http://svc-combinatorial-mcp.internal:8000/sse"
    clearance: "PUBLIC"
```

---

## 4. The Architectural Victory

By executing this extraction:

1. **`coreason-manifest`** loses its `clingo` dependency. It is now a 100% pure Python AST library.
2. **`coreason-runtime`** is protected from C-level segmentation faults. If the `clingo` solver crashes or enters an infinite loop, it only takes down the isolated MCP container. The main Temporal Kinetic workflow remains flawlessly stable.
3. **`coreason-ecosystem`** blindly routes the payload. It doesn't need to know what "Answer Set Programming" is; it just routes `urn:coreason:oracle:combinatorial` to the container and enforces the RFC 8785 cryptographic seal.
