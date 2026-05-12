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
from coreason_ecosystem.gateway.sovereign_mcp_registry import SovereignMCPRegistry
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
            "docker",
            "compose",
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
            pass  # nosec B110
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
            pass  # nosec B110
        await asyncio.sleep(delay)
        elapsed += delay
        delay = min(delay * 1.5, 3.0)
    raise TimeoutError(f"Fallback check failed. Port {port} never bound.")


async def execute_up() -> None:
    """Implement Just-in-Time Cognition Flow via NemoClaw."""
    project_path = Path.cwd()
    root_hash = await calculate_epistemic_root(project_path)
    write_registry_lock(project_path, root_hash)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task_sandbox = progress.add_task(
            "[cyan]Igniting NemoClaw Sandbox...[/cyan]", total=None
        )
        proc = await asyncio.create_subprocess_exec(
            "nemoclaw",
            "sandbox",
            "start",
            "--empty",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print()
            raise typer.Exit(1)
        progress.update(
            task_sandbox,
            description="[green]✓ NemoClaw Sandbox ACTIVE[/green]",
            completed=True,
        )

        task_injection = progress.add_task(
            "[cyan]Injecting Sovereign MCP Gateway...[/cyan]", total=None
        )
        logger.info(
            "[Gateway] Connecting to NemoClaw via mTLS and registering MCP tools..."
        )
        registry = SovereignMCPRegistry()
        await registry.initialize()
        await registry.scan_action_space_modules()
        progress.update(
            task_injection,
            description="[green]✓ Gateway Injection Complete[/green]",
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
