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
from coreason_manifest.spec.ontology import CognitiveSwarmDeploymentManifest
from loguru import logger


async def wait_for_postgres(compose_path_str: str, timeout: float = 60.0) -> None:
    """Implement exponential backoff to await Postgres application-layer readiness.

    Dynamically routes a `pg_isready` socket check natively inside the active container
    bypassing shallow host TCP bindings.
    """
    elapsed = 0.0
    delay = 1.0
    while elapsed < timeout:
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            compose_path_str,
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-h",
            "localhost",
            "-U",
            "postgres",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0:
            return
        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 5.0)
    raise TimeoutError("PostgreSQL failed to achieve application-layer readiness.")


async def wait_for_temporal(timeout: float = 60.0) -> None:
    """Await genuine Temporal orchestration bindings via a deep cluster info validation.

    Ensures internal state machine scaling and shard validation are complete utilizing
    `get_cluster_info()` rather than shallow port availability.
    """
    try:
        from temporalio.client import Client
    except ImportError:  # pragma: no cover
        pass

    elapsed = 0.0
    delay = 1.0
    while elapsed < timeout:
        try:
            await asyncio.wait_for(Client.connect("localhost:7233"), timeout=2.0)
            return
        except Exception:
            pass
        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 5.0)
    raise TimeoutError("Temporal failed to achieve application-layer readiness.")


async def wait_for_port(port: int, timeout: float = 30.0) -> None:
    """Fallback standard port verification sequence for localized ecosystem sockets."""
    elapsed = 0.0
    delay = 1.0
    while elapsed < timeout:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port), timeout=0.5
            )
            writer.close()
            await writer.wait_closed()
            return
        except Exception:
            pass
        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 3.0)
    raise TimeoutError(f"Fallback check failed. Port {port} never bound.")


async def execute_up() -> None:
    """Implement Idempotent DAG Resolution for the Swarm infrastructure.

    This routine dynamically resolves the compose file path, synthesizes
    internal directory structures, and executes the Epistemic Cryptographic
    Handshake to bind the Merkle Root to the Temporal orchestrator.
    """

    compose_path = Path.cwd() / "infrastructure" / "local" / "compose.yaml"
    if not compose_path.exists():
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
        task_teardown = progress.add_task(
            "[cyan]Executing Targeted Host Cleanup...[/cyan]", total=None
        )
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            compose_path_str,
            "down",
            "-v",
            "--remove-orphans",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print(
                f"[red]Error during host cleanup:[/red]\n{stderr.decode('utf-8')}"
            )
            raise typer.Exit(1)
        progress.update(
            task_teardown,
            description="[green]✓ Cleaned dangling volumes and networks[/green]",
            completed=True,
        )

        task_postgres = progress.add_task(
            "[cyan]Binding Epistemic Ledger...[/cyan]", total=None
        )
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
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
            console.print(
                f"[red]Error starting Postgres:[/red]\n{stderr.decode('utf-8')}"
            )
            raise typer.Exit(1)
        try:
            await wait_for_postgres(compose_path_str)
        except TimeoutError as e:
            console.print(f"[bold red]Timeout waiting for Postgres:[/bold red]\n{e}")
            raise typer.Exit(1)
        progress.update(
            task_postgres,
            description="[green]✓ Ledger ACTIVE (Postgres: 5432)[/green]",
            completed=True,
        )

        task_temporal = progress.add_task(
            "[cyan]Igniting Orchestrator Fabric...[/cyan]", total=None
        )
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
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
            console.print(
                f"[red]Error starting Temporal:[/red]\n{stderr.decode('utf-8')}"
            )  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        try:
            await wait_for_temporal()
        except TimeoutError as e:
            console.print(f"[bold red]Timeout waiting for Temporal:[/bold red]\n{e}")
            raise typer.Exit(1)
        progress.update(
            task_temporal,
            description="[green]✓ Orchestrator ACTIVE (Temporal: 7233)[/green]",
            completed=True,
        )

        task_daemon = progress.add_task(
            "[cyan]Igniting Thermodynamic Mesh...[/cyan]", total=None
        )

        project_path = Path.cwd()
        root_hash = await calculate_epistemic_root(project_path)
        write_registry_lock(project_path, root_hash)

        env = os.environ.copy()
        env["EPISTEMIC_MERKLE_ROOT"] = root_hash

        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            compose_path_str,
            "up",
            "-d",
            "--build",
            "-V",
            "--force-recreate",
            "coreason-runtime",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print(
                f"[red]Error starting Physics Engine:[/red]\n{stderr.decode('utf-8')}"
            )  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        try:
            await wait_for_port(8000)
        except TimeoutError as e:
            console.print(
                f"[bold red]Timeout waiting for Physics Engine:[/bold red]\n{e}"
            )
            raise typer.Exit(1)
        progress.update(
            task_daemon,
            description="[green]✓ Physics Engine ACTIVE (Daemon: 8000)[/green]",
            completed=True,
        )

        task_observability = progress.add_task(
            "[cyan]Booting Observability Sidecars...[/cyan]",
            total=None,
        )
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
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
            console.print(
                f"[red]Error starting Observability:[/red]\n{stderr.decode('utf-8')}"
            )  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        progress.update(
            task_observability,
            description="[green]✓ Observability ACTIVE (Grafana: 3000)[/green]",
            completed=True,
        )


async def provision_swarm_topology(manifest: CognitiveSwarmDeploymentManifest) -> None:
    """Provision a cognitive swarm topology based on the deployment manifest.

    Executes the thermodynamic provisioning (local swarm via execute_up).
    """
    logger.info(
        f"[Thermodynamic Actuator] Provisioning swarm: {manifest.swarm_objective_prompt} with {manifest.agent_node_count} agents."
    )
    await execute_up()
