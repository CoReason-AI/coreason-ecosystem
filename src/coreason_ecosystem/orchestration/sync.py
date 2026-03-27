# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import json
import subprocess
from pathlib import Path

from rich.status import Status

from coreason_ecosystem.cli import console
from coreason_ecosystem.orchestration.build import execute_build
from coreason_ecosystem.orchestration.registry import calculate_epistemic_root, write_registry_lock


async def execute_sync() -> None:
    """Autonomically heal Ontological Drift."""

    project_path = Path.cwd()

    with Status("[cyan]Detecting Drift...[/cyan]", console=console) as status:
        # 1. Semantic Sync
        status.update("[yellow]Regenerating Ontology...[/yellow]")
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Swarm Ontology"}
        schema_path = project_path / "coreason_ontology.schema.json"
        with schema_path.open("w", encoding="utf-8") as f:
            json.dump(schema, f, indent=4)

        # 2. Physical Sync
        status.update("[magenta]Re-crystallizing Capabilities...[/magenta]")
        await execute_build(str(project_path))

        # 3. Registry Sync
        status.update("[blue]Syncing Epistemic Registry...[/blue]")
        root_hash = await calculate_epistemic_root(project_path)
        write_registry_lock(project_path, root_hash)

        # 4. Thermodynamic Restart
        status.update("[red]Initiating Thermodynamic Restart...[/red]")
        compose_path = Path(__file__).parent.parent.parent.parent / "infrastructure" / "local" / "compose.yaml"
        if not compose_path.exists():
            compose_path = project_path / "infrastructure" / "local" / "compose.yaml"

        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_path.resolve()),
                "restart",
                "coreason-runtime",
            ],
            check=False,
        )

        status.update("[green]Swarm Restored.[/green]")
        console.print("[bold green]✓ Autopoietic Healing Complete[/bold green]")
