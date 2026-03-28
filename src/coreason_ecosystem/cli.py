# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import asyncio
import importlib.metadata
import sys
from typing import Any

import typer
from rich.console import Console

console = Console()


def global_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: Any,
) -> None:  # pragma: no cover
    console.print(f"[bold red]✗ Fatal Execution Error:[/bold red] {exc_value}")
    sys.exit(1)


sys.excepthook = global_excepthook


def version_callback(value: bool) -> None:  # pragma: no cover
    if value:
        try:
            version = importlib.metadata.version("coreason-ecosystem")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown (local development)"
        console.print(f"[bold cyan]CoReason Ecosystem[/bold cyan] v{version}")
        raise typer.Exit()


# We need to initialize the app first
app = typer.Typer(help="CoReason Meta-Orchestrator Control Plane")


@app.callback()
def cli_callback(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Show the active hypervisor version.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:  # pragma: no cover
    """The Autopoietic Hypervisor for the Tripartite Cybernetic Manifold."""
    pass


# We must import the commands after 'console' and 'app' are defined,
# but to avoid circular dependencies where submodules import 'console'
# from cli.py, 'console' is defined above first.
from coreason_ecosystem.orchestration.build import execute_build  # noqa: E402
from coreason_ecosystem.orchestration.doctor import execute_doctor  # noqa: E402
from coreason_ecosystem.orchestration.init import execute_init  # noqa: E402
from coreason_ecosystem.orchestration.sync import execute_sync  # noqa: E402
from coreason_ecosystem.orchestration.up import execute_up  # noqa: E402


@app.command(
    name="init",
    help="Autonomically generate a mathematically verified Swarm workspace.",
)
def init(
    project_name: str = typer.Argument(...),
    topology: str = typer.Option("base", help="Target topology (base, medallion, rag)"),
) -> None:
    """Autonomically generate a mathematically verified Swarm workspace."""
    with console.status("[bold green]Synthesizing Ontological Boundaries...") as status:
        asyncio.run(execute_init(project_name, topology))
        status.update("[bold green]Wiring Sensory Cortex...")
        status.update("[bold green]Initializing Immunological Hooks...")
    console.print(
        f"[bold blue]Workspace '{project_name}' mathematically sealed and ready.[/bold blue]"
    )


@app.command(name="build")
def build(
    target_path: str = typer.Argument(
        ..., help="Path to the capability script to compile."
    ),
) -> None:
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


@app.command(
    name="sync",
    help="Autonomically heal Ontological Drift by synchronizing schemas, recompiling capabilities, and restarting the daemon.",
)
def sync() -> None:
    """Autonomically heal Ontological Drift."""
    asyncio.run(execute_sync())


def main() -> None:  # pragma: no cover
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
