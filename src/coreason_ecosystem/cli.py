# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import asyncio

import typer
from rich.console import Console

console = Console()

# We need to initialize the app first
app = typer.Typer(help="CoReason Meta-Orchestrator Control Plane")

# We must import the commands after 'console' and 'app' are defined,
# but to avoid circular dependencies where submodules import 'console'
# from cli.py, 'console' is defined above first.
from coreason_ecosystem.orchestration.build import execute_build  # noqa: E402
from coreason_ecosystem.orchestration.doctor import execute_doctor  # noqa: E402
from coreason_ecosystem.orchestration.up import execute_up  # noqa: E402


@app.command(name="build")
def build(target_path: str = typer.Argument(..., help="Path to the capability script to compile.")) -> None:
    """Compile human-readable Python capabilities into WASM boundaries and calculate their Epistemic Seals."""
    asyncio.run(execute_build(target_path))


@app.command(name="up")
def up() -> None:
    """Implement Idempotent DAG Resolution for the Swarm infrastructure."""
    asyncio.run(execute_up())


@app.command(name="doctor")
def doctor() -> None:
    """Prove Ontological Isomorphism across the Tripartite Manifold."""
    asyncio.run(execute_doctor())


def main() -> None:  # pragma: no cover
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
