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
import os
import subprocess
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from coreason_ecosystem.cli import console
from coreason_ecosystem.orchestration.registry import (
    calculate_epistemic_root,
    write_registry_lock,
)


async def is_port_bound(port: int) -> bool:
    """Check if a specific TCP port is currently bound."""
    # We can perform a non-blocking check by using a quick socket connect.
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port), timeout=0.1
        )
        writer.close()
        await writer.wait_closed()
        return True
    except ConnectionRefusedError, TimeoutError, OSError:
        return False


async def execute_up() -> None:
    """Implement Idempotent DAG Resolution for the Swarm infrastructure."""

    # Resolve the compose file path dynamically
    compose_path = Path.cwd() / "infrastructure" / "local" / "compose.yaml"
    if not compose_path.exists():
        # Fallback to resolving relative to the project root assuming the file is deeply nested during execution
        compose_path = (
            Path(__file__).parent.parent.parent.parent
            / "infrastructure"
            / "local"
            / "compose.yaml"
        )

    compose_path_str = str(compose_path.resolve())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        # Node 1: Epistemic Ledger (Postgres)
        task_postgres = progress.add_task(
            "[yellow]Checking Ledger (Postgres: 5432)...[/yellow]", total=None
        )
        if await is_port_bound(5432):
            progress.update(
                task_postgres,
                description="[green]✓ Ledger ACTIVE (Postgres: 5432)[/green]",
                completed=True,
            )
        else:
            progress.update(
                task_postgres,
                description="[cyan]Binding Epistemic Ledger...[/cyan]",
            )
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "compose",
                "-f",
                compose_path_str,
                "up",
                "-d",
                "postgres",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.communicate()
            progress.update(
                task_postgres,
                description="[green]✓ Ledger ACTIVE (Postgres: 5432)[/green]",
                completed=True,
            )

        # Node 2: Orchestration Fabric (Temporal)
        task_temporal = progress.add_task(
            "[yellow]Checking Orchestrator (Temporal: 7233)...[/yellow]", total=None
        )
        if await is_port_bound(7233):
            progress.update(
                task_temporal,
                description="[green]✓ Orchestrator ACTIVE (Temporal: 7233)[/green]",
                completed=True,
            )
        else:
            progress.update(
                task_temporal,
                description="[cyan]Igniting Thermodynamic Mesh...[/cyan]",
            )
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "compose",
                "-f",
                compose_path_str,
                "up",
                "-d",
                "temporal",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.communicate()
            progress.update(
                task_temporal,
                description="[green]✓ Orchestrator ACTIVE (Temporal: 7233)[/green]",
                completed=True,
            )

        # Node 3: Physics Engine (Daemon)
        task_daemon = progress.add_task(
            "[yellow]Checking Physics Engine (Daemon: 8000)...[/yellow]", total=None
        )
        if await is_port_bound(8000):
            progress.update(
                task_daemon,
                description="[green]✓ Physics Engine ACTIVE (Daemon: 8000)[/green]",
                completed=True,
            )
        else:
            progress.update(
                task_daemon,
                description="[cyan]Igniting Thermodynamic Mesh...[/cyan]",
            )

            # The Cryptographic Handshake
            project_path = Path.cwd()
            root_hash = await calculate_epistemic_root(project_path)
            write_registry_lock(project_path, root_hash)

            env = os.environ.copy()
            env["EPISTEMIC_MERKLE_ROOT"] = root_hash

            proc = await asyncio.create_subprocess_exec(
                "docker",
                "compose",
                "-f",
                compose_path_str,
                "up",
                "-d",
                "coreason-runtime",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            await proc.communicate()
            progress.update(
                task_daemon,
                description="[green]✓ Physics Engine ACTIVE (Daemon: 8000)[/green]",
                completed=True,
            )

        # Node 4: Observability Sidecars (Prometheus & Grafana)
        task_observability = progress.add_task(
            "[yellow]Checking Observability Sidecars (Grafana: 3000)...[/yellow]",
            total=None,
        )
        if await is_port_bound(3000):
            progress.update(
                task_observability,
                description="[green]✓ Observability ACTIVE (Grafana: 3000)[/green]",
                completed=True,
            )
        else:
            progress.update(
                task_observability,
                description="[cyan]Booting Observability Sidecars...[/cyan]",
            )
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "compose",
                "-f",
                compose_path_str,
                "up",
                "-d",
                "prometheus",
                "grafana",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.communicate()
            progress.update(
                task_observability,
                description="[green]✓ Observability ACTIVE (Grafana: 3000)[/green]",
                completed=True,
            )
