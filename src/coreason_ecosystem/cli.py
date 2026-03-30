# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

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
    from coreason_ecosystem.utils.logger import logger

    # 1. Log the critical error to the mesh (JSON + OTLP)
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
        f"Fatal Execution Error: {exc_value}"
    )

    # 2. Print to the operator's terminal
    console.print(f"[bold red]✗ Fatal Execution Error:[/bold red] {exc_value}")
    sys.exit(1)


sys.excepthook = global_excepthook


def version_callback(value: bool) -> None:
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
) -> None:
    """The Autopoietic Hypervisor for the Tripartite Cybernetic Manifold."""
    pass


# We must import the commands after 'console' and 'app' are defined,
# but to avoid circular dependencies where submodules import 'console'
# from cli.py, 'console' is defined above first.
from pathlib import Path  # noqa: E402
from coreason_ecosystem.orchestration.build import execute_build  # noqa: E402
from coreason_ecosystem.orchestration.doctor import execute_doctor  # noqa: E402
from coreason_ecosystem.orchestration.init import execute_init  # noqa: E402
from coreason_ecosystem.orchestration.sync import execute_sync  # noqa: E402
from coreason_ecosystem.orchestration.up import execute_up  # noqa: E402
from coreason_ecosystem.fleet.daemon import AutonomicFleetManager  # noqa: E402

fleet_app = typer.Typer()
app.add_typer(fleet_app, name="fleet", help="Manage the autonomic compute fleet.")


@fleet_app.command("start")
def fleet_start(
    mesh_auth_key: str = typer.Option(..., help="The ephemeral Tailscale/Headscale auth key"),
    temporal_mesh_ip: str = typer.Option(..., help="The internal 10.x.x.x IP of the Medallion State Engine"),
    max_budget_hr: float = typer.Option(5.0, help="Max budget per hour"),
    polling_interval: int = typer.Option(10, help="Polling interval in seconds"),
) -> None:  # pragma: no cover
    templates_path = Path.cwd() / "infrastructure" / "ephemeral"
    manager = AutonomicFleetManager(
        max_budget_hr=max_budget_hr,
        polling_interval_sec=polling_interval,
        templates_path=templates_path.resolve(),
        mesh_auth_key=mesh_auth_key,
        temporal_mesh_ip=temporal_mesh_ip,
    )
    asyncio.run(manager.start())


@app.command(
    name="init",
    help="Autonomically generate a mathematically verified Swarm workspace.",
)
def init(
    project_name: str = typer.Argument(...),
    topology: str = typer.Option("base", help="Target topology (base, medallion, rag)"),
    lang: str = typer.Option("python", help="Target language (python, rust, go)"),
) -> None:
    """Autonomically generate a mathematically verified Swarm workspace."""
    from coreason_ecosystem.utils.telemetry import (
        start_otlp_background_worker,
        stop_otlp_background_worker,
    )

    async def _run() -> None:
        start_otlp_background_worker()
        try:
            await execute_init(project_name, topology, lang)
        finally:
            await stop_otlp_background_worker()

    with console.status("[bold green]Synthesizing Ontological Boundaries...") as status:
        asyncio.run(_run())
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
    from coreason_ecosystem.utils.telemetry import (
        start_otlp_background_worker,
        stop_otlp_background_worker,
    )

    async def _run() -> None:
        start_otlp_background_worker()
        try:
            await execute_build(target_path)
        finally:
            await stop_otlp_background_worker()

    asyncio.run(_run())


@app.command(name="up")
def up() -> None:
    """Implement Idempotent DAG Resolution for the Swarm infrastructure."""
    from coreason_ecosystem.utils.telemetry import (
        start_otlp_background_worker,
        stop_otlp_background_worker,
    )

    async def _run() -> None:
        start_otlp_background_worker()
        try:
            await execute_up()
        finally:
            await stop_otlp_background_worker()

    asyncio.run(_run())


@app.command(name="doctor")
def doctor() -> None:
    """Prove Ontological Isomorphism across the Tripartite Manifold."""
    from coreason_ecosystem.utils.telemetry import (
        start_otlp_background_worker,
        stop_otlp_background_worker,
    )

    async def _run() -> None:
        start_otlp_background_worker()
        try:
            await execute_doctor()
        finally:
            await stop_otlp_background_worker()

    asyncio.run(_run())


@app.command(
    name="sync",
    help="Autonomically heal Ontological Drift by synchronizing schemas, recompiling capabilities, and restarting the daemon.",
)
def sync() -> None:
    """Autonomically heal Ontological Drift."""
    from coreason_ecosystem.utils.telemetry import (
        start_otlp_background_worker,
        stop_otlp_background_worker,
    )

    async def _run() -> None:
        start_otlp_background_worker()
        try:
            await execute_sync()
        finally:
            await stop_otlp_background_worker()

    asyncio.run(_run())


def main() -> None:  # pragma: no cover
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
