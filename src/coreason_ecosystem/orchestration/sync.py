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

import typer
from rich.status import Status

from coreason_ecosystem.cli import console
from coreason_ecosystem.orchestration.registry import (
    calculate_epistemic_root,
    write_registry_lock,
)


async def execute_sync() -> None:
    """Autonomically heal Ontological Drift."""

    project_path = Path.cwd()

    with Status("[cyan]Detecting Drift...[/cyan]", console=console) as status:

        # 3. Registry Sync
        status.update("[blue]Syncing Epistemic Registry...[/blue]")
        root_hash = await calculate_epistemic_root(project_path)
        write_registry_lock(project_path, root_hash)

        # 4. Thermodynamic Restart
        status.update("[red]Initiating Thermodynamic Restart...[/red]")
        compose_path = project_path / "infrastructure" / "local" / "compose.yaml"
        if not compose_path.exists():
            compose_path = (
                Path(__file__).parent.parent.parent.parent
                / "infrastructure"
                / "local"
                / "compose.yaml"
            )
            if not compose_path.exists():
                console.print(
                    "[bold red]Error: Could not locate compose.yaml in workspace or fallback path.[/bold red]"
                )
                raise typer.Exit(1)

        import shutil

        docker_bin = shutil.which("docker") or "docker"

        env = os.environ.copy()
        env["EPISTEMIC_MERKLE_ROOT"] = root_hash

        process = await asyncio.create_subprocess_exec(
            docker_bin,
            "compose",
            "-f",
            str(compose_path.resolve()),
            "up",
            "-d",
            "coreason-runtime",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            console.print(f"[bold red]Error starting coreason-runtime:[/bold red]\n[bold red]{stderr.decode('utf-8')}[/bold red]")
            raise typer.Exit(1)

        status.update("[green]Swarm Restored.[/green]")
        console.print("[bold green]✓ Autopoietic Healing Complete[/bold green]")
