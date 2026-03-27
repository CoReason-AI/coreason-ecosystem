# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import hashlib
import json
from pathlib import Path

from rich.panel import Panel

from coreason_ecosystem.cli import console


async def execute_build(target_path: str) -> None:
    """
    Compile human-readable Python capabilities into WASM boundaries and calculate their Epistemic Seals.
    """
    target = Path(target_path)
    if not target.exists():
        console.print(
            f"[bold red]Error:[/bold red] Target path {target_path} does not exist."
        )
        return

    # Determine files to process
    if target.is_dir():
        cap_dir = target / "src" / "capabilities"
        if cap_dir.exists():
            files_to_build = list(cap_dir.rglob("*.py"))
        else:
            files_to_build = list(target.rglob("*.py"))
    else:
        files_to_build = [target]

    if not files_to_build:
        console.print(
            f"[yellow]Warning:[/yellow] No capabilities found to build in {target_path}."
        )
        return

    # Ensure the .coreason directory exists in the user's current working directory
    coreason_dir = Path.cwd() / ".coreason"
    coreason_dir.mkdir(parents=True, exist_ok=True)

    # Load existing ledger
    ledger_path = coreason_dir / "capability_ledger.json"
    ledger_data = {}
    if ledger_path.exists():
        try:
            with ledger_path.open("r", encoding="utf-8") as f:
                ledger_data = json.load(f)
        except json.JSONDecodeError:
            ledger_data = {}

    for file_path in files_to_build:
        # 1. Simulate an AOT compilation or bundling of the target Python file
        # For now, simply read the file's bytes.
        content = file_path.read_bytes()

        # 2. Calculate the cryptographic SHA-256 hash of the file/bundle
        file_hash = hashlib.sha256(content).hexdigest()

        # 3. Store the hash using target path as key
        ledger_data[str(file_path.resolve())] = file_hash

        # Output the calculated Epistemic Seal (hash) to the terminal
        panel = Panel(
            f"[green]Capability Crystallized:[/green]\n[cyan]{file_path.resolve()}[/cyan]\n\n"
            f"[bold]Epistemic Seal (SHA-256):[/bold]\n[yellow]{file_hash}[/yellow]",
            title="[bold blue]Build Complete[/bold blue]",
            expand=False,
        )
        console.print(panel)

    # 4. Register the hash into .coreason/capability_ledger.json
    with ledger_path.open("w", encoding="utf-8") as f:
        json.dump(ledger_data, f, indent=4)
