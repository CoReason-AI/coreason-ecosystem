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
import shutil
import subprocess
from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from coreason_ecosystem.cli import console
from coreason_ecosystem.orchestration.registry import (
    calculate_epistemic_root,
    write_registry_lock,
)


async def execute_up() -> None:
    """Implement Idempotent DAG Resolution for the Swarm infrastructure."""

    # Resolve the compose file path dynamically
    compose_path = Path.cwd() / "infrastructure" / "local" / "compose.yaml"
    if not compose_path.exists():
        # Read the internal compose file, create dirs, and copy it
        internal_compose_path = (
            Path(__file__).parent.parent.parent.parent
            / "infrastructure"
            / "local"
            / "compose.yaml"
        )
        compose_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(internal_compose_path, compose_path)

    compose_path_str = str(compose_path.resolve())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        # Node 1: Epistemic Ledger (Postgres)
        task_postgres = progress.add_task(
            "[cyan]Binding Epistemic Ledger...[/cyan]", total=None
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
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print(f"[red]Error starting Postgres:[/red]\n{stderr.decode('utf-8')}")
            raise typer.Exit(1)
        progress.update(
            task_postgres,
            description="[green]✓ Ledger ACTIVE (Postgres: 5432)[/green]",
            completed=True,
        )

        # Node 2: Orchestration Fabric (Temporal)
        task_temporal = progress.add_task(
            "[cyan]Igniting Orchestrator Fabric...[/cyan]", total=None
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
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print(f"[red]Error starting Temporal:[/red]\n{stderr.decode('utf-8')}")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        progress.update(
            task_temporal,
            description="[green]✓ Orchestrator ACTIVE (Temporal: 7233)[/green]",
            completed=True,
        )

        # Node 3: Physics Engine (Daemon)
        task_daemon = progress.add_task(
            "[cyan]Igniting Thermodynamic Mesh...[/cyan]", total=None
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
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print(f"[red]Error starting Physics Engine:[/red]\n{stderr.decode('utf-8')}")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        progress.update(
            task_daemon,
            description="[green]✓ Physics Engine ACTIVE (Daemon: 8000)[/green]",
            completed=True,
        )

        # Node 4: Observability Sidecars (Prometheus & Grafana)
        task_observability = progress.add_task(
            "[cyan]Booting Observability Sidecars...[/cyan]",
            total=None,
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
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print(f"[red]Error starting Observability:[/red]\n{stderr.decode('utf-8')}")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        progress.update(
            task_observability,
            description="[green]✓ Observability ACTIVE (Grafana: 3000)[/green]",
            completed=True,
        )
