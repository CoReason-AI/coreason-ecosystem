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


sys.excepthook = global_excepthook  # pragma: no cover


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
from coreason_ecosystem.orchestration.isomorphism_probe import execute_oracle_diagnostic  # noqa: E402
from coreason_ecosystem.orchestration.sync import execute_sync  # noqa: E402
from coreason_ecosystem.orchestration.up import execute_up  # noqa: E402
from coreason_ecosystem.fleet.daemon import AutonomicFleetManager  # noqa: E402

fleet_app = typer.Typer()
app.add_typer(
    fleet_app, name="fleet", help="Manage the autonomic Cognitive Entity compute fleet."
)


@fleet_app.command("start")
def fleet_start(
    max_budget_hr: float = typer.Option(5.0, help="Max budget per hour"),
    polling_interval: int = typer.Option(10, help="Polling interval in seconds"),
) -> None:  # pragma: no cover
    templates_path = Path.cwd() / "infrastructure" / "ephemeral"
    manager = AutonomicFleetManager(
        max_budget_hr=max_budget_hr,
        polling_interval_sec=polling_interval,
        templates_path=templates_path.resolve(),
    )
    asyncio.run(manager.start())


@app.command(name="up")
def up() -> None:
    """Implement Idempotent DAG Resolution for the Swarm infrastructure."""

    async def _run() -> None:  # pragma: no cover
        await execute_up()

    asyncio.run(_run())


@app.command(name="doctor")
def doctor() -> None:
    """Prove Ontological Isomorphism across the Tripartite Manifold."""

    async def _run() -> None:
        await execute_oracle_diagnostic()

    asyncio.run(_run())


@app.command(
    name="sync",
    help="Autonomically heal Ontological Drift by synchronizing schemas, recompiling capabilities, and restarting the daemon.",
)
def sync() -> None:
    """Autonomically heal Ontological Drift."""

    async def _run() -> None:
        await execute_sync()

    asyncio.run(_run())


docs_app = typer.Typer(help="Epistemic Documentation Pipeline")
app.add_typer(docs_app, name="docs")

license_app = typer.Typer(help="Sovereign Commercial License Management")
app.add_typer(license_app, name="license")

distr_app = typer.Typer(help="Distr Internal Billing & Provisioning Backend")
app.add_typer(distr_app, name="distr")


@distr_app.command("init-vault")
def distr_init_vault() -> None:
    """The Key Generation Ceremony: Generate and vault the Master Cryptographic Keys."""
    from coreason_ecosystem.auth.distr_provisioning import init_vault

    try:
        init_vault()
        console.print(
            "[bold green]✓ Key Generation Ceremony Complete. Vault initialized.[/bold green]"
        )
    except Exception as e:
        console.print(f"[bold red]✗ Vault Initialization Failed:[/bold red] {e}")


@distr_app.command("issue-license")
def distr_issue_license(
    tenant_cid: str = typer.Option(
        ..., help="The client's Tenant ID (e.g., 'tenant-xyz')"
    ),
    entitlements: list[str] = typer.Option(
        ["COMMERCIAL_USE"],
        help="List of entitlements (e.g., 'COMMERCIAL_USE', 'PRIVATE_LEDGER')",
    ),
    valid_days: int = typer.Option(365, help="Validity duration in days"),
    hardware_zk_proof: str = typer.Option(
        None, help="Optional zk-SNARK proof for hardware binding"
    ),
) -> None:
    """Issue a CommercialOverrideReceipt (Signed VCDM v2.0 JWT) for a client."""
    from coreason_ecosystem.auth.distr_provisioning import issue_license

    try:
        token = issue_license(tenant_cid, entitlements, valid_days, hardware_zk_proof)
        console.print(
            "[bold green]✓ CommercialOverrideReceipt Issued Successfully.[/bold green]\n"
        )
        console.print(f"[bold cyan]Token:[/bold cyan] {token}")
    except Exception as e:
        console.print(f"[bold red]✗ License Issuance Failed:[/bold red] {e}")


@distr_app.command("serve-api")
def distr_serve_api(
    port: int = typer.Option(8000, help="Port to run the Distr API on"),
    host: str = typer.Option("127.0.0.1", help="Host IP to bind to"),
) -> None:
    """Run the Distr FastAPI backend for the Vite Web Dashboard."""
    import uvicorn

    console.print(
        f"[bold green]Starting Distr API on http://{host}:{port}[/bold green]"
    )
    uvicorn.run(
        "coreason_ecosystem.auth.distr_api:app", host=host, port=port, reload=True
    )


@license_app.command("install")
def license_install(
    jwt_string: str = typer.Argument(
        ..., help="The cryptographically signed JWT License Token."
    ),
) -> None:
    """Install and mathematically verify a Commercial License JWT."""
    from coreason_ecosystem.auth.license_validator import install_license

    try:
        install_license(jwt_string)
        console.print(
            "[bold green]✓ Commercial License installed and mathematically verified.[/bold green]"
        )
    except Exception as e:
        console.print(f"[bold red]✗ License Installation Failed:[/bold red] {e}")


@docs_app.command(name="build")
def build_docs_cmd() -> None:
    """Generate dynamic MkDocs documentation from the ontological schema and ledger."""
    try:
        from coreason_ecosystem.docs_generator import generate_dynamic_docs

        generate_dynamic_docs()
    except Exception as e:
        console.print(f"[bold red]Documentation Pipeline Failed:[/bold red] {e}")


@app.command(name="pi")
def pi_terminal() -> None:
    """Launch the pi.dev Sovereign Developer Console."""
    import subprocess  # nosec: B404

    console.print("[bold green]Launching the pi.dev Kinetic Harness...[/bold green]")
    try:
        # We invoke the pi.dev CLI natively using npx
        subprocess.run(["npx", "@mariozechner/pi-coding-agent"], check=True)  # nosec: B603, B607
    except FileNotFoundError:
        console.print(
            "[bold red]Error:[/bold red] Node.js and npx are required to launch pi.dev."
        )
    except subprocess.CalledProcessError as e:
        console.print(
            f"[bold red]Pi terminal exited with code {e.returncode}[/bold red]"
        )


def main() -> None:  # pragma: no cover
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
