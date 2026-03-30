# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import hashlib
import os
from pathlib import Path

import httpx
from rich.table import Table

from coreason_ecosystem.cli import console
from coreason_ecosystem.orchestration.registry import calculate_epistemic_root, read_registry_lock


async def execute_doctor() -> None:
    """Prove Ontological Isomorphism across the Tripartite Manifold."""
    base_url = os.environ.get("COREASON_RUNTIME_URL", "http://localhost:8000").rstrip("/")

    table = Table(title="[bold blue]Ontological Isomorphism Diagnostic[/bold blue]")
    table.add_column("System Boundary", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Telemetry/Hash", style="green")

    async with httpx.AsyncClient() as client:
        # Probe A: Runtime Integrity
        try:
            resp = await client.get(f"{base_url}/docs", timeout=2.0)
            if resp.status_code == 200:
                status_a = "[green]✓ ALIVE[/green]"
                latency_a = f"{resp.elapsed.total_seconds() * 1000:.1f}ms"
            else:
                status_a = f"[red]✗ ERROR {resp.status_code}[/red]"
                latency_a = "N/A"
        except (httpx.RequestError, httpx.TimeoutException):
            status_a = "[red]✗ OFFLINE[/red]"
            latency_a = "N/A"

        table.add_row("Runtime Daemon", status_a, latency_a)

        # Probe B: Telemetry Mesh
        try:
            # Check telemetry endpoint without blocking indefinitely.
            # We assume it streams, so getting a 200 on connect proves it's alive.
            async with client.stream(
                "GET", f"{base_url}/api/v1/telemetry/stream", timeout=5.0
            ) as resp:
                if resp.status_code == 200:
                    status_b = "[green]✓ STREAMING[/green]"
                    latency_b = "Connected"
                else:
                    status_b = f"[red]✗ ERROR {resp.status_code}[/red]"
                    latency_b = "N/A"
        except (httpx.RequestError, httpx.TimeoutException):
            status_b = "[red]✗ TIMEOUT/OFFLINE[/red]"
            latency_b = "N/A"

        table.add_row("Telemetry Mesh", status_b, latency_b)

        # Probe C: Schema Sync
        schema_path = Path.cwd() / "coreason_ontology.schema.json"

        if schema_path.exists():
            schema_bytes = schema_path.read_bytes()
            schema_hash = hashlib.sha256(schema_bytes).hexdigest()
            status_c = "[green]✓ SYNCED[/green]"
            latency_c = schema_hash[:16] + "..."
        else:
            status_c = "[red]✗ MISSING[/red]"
            latency_c = "N/A"

        table.add_row("Ontology Schema", status_c, latency_c)

        # Probe D: Epistemic Isomorphism
        local_root = read_registry_lock(Path.cwd())
        if local_root is None:
            local_root = "0" * 64

        current_root = await calculate_epistemic_root(Path.cwd())

        if current_root != local_root:
            status_d = "[red]✗ LOCAL DRIFT DETECTED[/red]"
            latency_d = "Run 'coreason build'"
        else:
            try:
                resp = await client.get(
                    f"{base_url}/api/v1/epistemic/verify",
                    headers={"X-Epistemic-Root": local_root},
                    timeout=2.0,
                )
                if resp.status_code == 200:
                    status_d = "[green]✓ ALIGNED[/green]"
                    latency_d = (
                        local_root[:16] + "..." if len(local_root) > 16 else local_root
                    )
                elif resp.status_code == 409:
                    status_d = "[red]✗ DRIFT DETECTED[/red]"
                    latency_d = "Run 'coreason sync'"
                else:
                    status_d = f"[yellow]⚠ HTTP {resp.status_code}[/yellow]"
                    latency_d = "Check Daemon"
            except (httpx.RequestError, httpx.TimeoutException):
                status_d = "[yellow]⚠ UNREACHABLE[/yellow]"
                latency_d = "Check Daemon"

        table.add_row("Epistemic Isomorphism", status_d, latency_d)

    console.print(table)
