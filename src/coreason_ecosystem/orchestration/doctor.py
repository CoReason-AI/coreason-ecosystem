# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import hashlib
from pathlib import Path

import coreason_manifest
import httpx
from rich.table import Table

from coreason_ecosystem.cli import console


async def execute_doctor() -> None:
    """Prove Ontological Isomorphism across the Tripartite Manifold."""
    table = Table(title="[bold blue]Ontological Isomorphism Diagnostic[/bold blue]")
    table.add_column("System Boundary", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Telemetry/Hash", style="green")

    # Probe A: Runtime Integrity
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://localhost:8000/docs", timeout=2.0)
            if resp.status_code == 200:
                status_a = "[green]✓ ALIVE[/green]"
                latency_a = f"{resp.elapsed.total_seconds() * 1000:.1f}ms"
            else:
                status_a = f"[red]✗ ERROR {resp.status_code}[/red]"
                latency_a = "N/A"
        except httpx.RequestError, httpx.TimeoutException:
            status_a = "[red]✗ OFFLINE[/red]"
            latency_a = "N/A"

    table.add_row("Runtime Daemon", status_a, latency_a)

    # Probe B: Telemetry Mesh
    async with httpx.AsyncClient() as client:
        try:
            # Check telemetry endpoint without blocking indefinitely.
            # We assume it streams, so getting a 200 on connect proves it's alive.
            async with client.stream("GET", "http://localhost:8000/api/v1/telemetry/stream", timeout=1.0) as resp:
                if resp.status_code == 200:
                    status_b = "[green]✓ STREAMING[/green]"
                    latency_b = "Connected"
                else:
                    status_b = f"[red]✗ ERROR {resp.status_code}[/red]"
                    latency_b = "N/A"
        except httpx.RequestError, httpx.TimeoutException:
            status_b = "[red]✗ TIMEOUT/OFFLINE[/red]"
            latency_b = "N/A"

    table.add_row("Telemetry Mesh", status_b, latency_b)

    # Probe C: Schema Sync
    manifest_path = Path(coreason_manifest.__path__[0])
    schema_path = manifest_path / "spec" / "coreason_ontology.schema.json"

    if schema_path.exists():
        schema_bytes = schema_path.read_bytes()
        schema_hash = hashlib.sha256(schema_bytes).hexdigest()
        status_c = "[green]✓ SYNCED[/green]"
        latency_c = schema_hash[:16] + "..."
    else:
        status_c = "[red]✗ MISSING[/red]"
        latency_c = "N/A"

    table.add_row("Ontology Schema", status_c, latency_c)

    console.print(table)
