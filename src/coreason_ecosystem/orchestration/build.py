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
import hashlib
import json
from pathlib import Path

import typer
from filelock import FileLock

from rich.panel import Panel

from coreason_ecosystem.cli import console


async def compile_and_hash(file_path: Path, bin_dir: Path) -> tuple[str, str]:
    try:
        rel_path = file_path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        rel_path = file_path.resolve()
    safe_name = "_".join(rel_path.parts)
    safe_name = Path(safe_name).with_suffix(".wasm").name
    wasm_out_path = bin_dir / safe_name
    module_name = str(file_path.with_suffix("")).replace("/", ".")

    try:
        compile_proc = await asyncio.create_subprocess_exec(
            "componentize-py",
            "-d", "wit",                 # Point to the wit directory you just created
            "-w", "example-world",       # The name of the world in your world.wit file
            "componentize",              # The required subcommand
            module_name,                 # The python app/module to componentize
            "-o", str(wasm_out_path),    # The output wasm binary
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await compile_proc.communicate()
    except FileNotFoundError:
        console.print(
            "[bold red]✗ Fatal Error: 'componentize-py' compiler not found.[/bold red]"
        )
        console.print(
            "Please install the WASM toolchain: [cyan]uv pip install componentize-py[/cyan]"
        )
        raise typer.Exit(1)

    if compile_proc.returncode != 0:
        console.print(f"[bold red]Error compiling {file_path}:[/bold red]")
        console.print(stderr.decode("utf-8", errors="replace"))
        raise typer.Exit(1)

    # 2. Calculate the cryptographic SHA-256 hash of the compiled file
    content = wasm_out_path.read_bytes()

    # 3. Store the hash using target path as key
    file_hash = hashlib.sha256(content).hexdigest()

    # Output the calculated Epistemic Seal (hash) to the terminal
    panel = Panel(
        f"[green]Capability Crystallized:[/green]\n[cyan]{rel_path}[/cyan]\n\n"
        f"[bold]Epistemic Seal (SHA-256):[/bold]\n[yellow]{file_hash}[/yellow]",
        title="[bold blue]Build Complete[/bold blue]",
        expand=False,
    )
    console.print(panel)

    return (str(rel_path), file_hash)


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
            potential_files = list(cap_dir.rglob("*.py"))
        else:
            potential_files = list(target.rglob("*.py"))
    else:
        potential_files = [target]

    # Filter files to only include those that are Extism capabilities
    files_to_build = []
    for file_path in potential_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            if "def main(" in content or "@validate_call" in content:
                files_to_build.append(file_path)
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not read {file_path}: {e}")

    if not files_to_build:
        console.print(
            f"[yellow]Warning:[/yellow] No capabilities found to build in {target_path}."
        )
        return

    # Ensure the .coreason directory exists in the user's current working directory
    coreason_dir = Path.cwd() / ".coreason"
    coreason_dir.mkdir(parents=True, exist_ok=True)

    bin_dir = coreason_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Compile files concurrently
    tasks = [compile_and_hash(file_path, bin_dir) for file_path in files_to_build]
    results = await asyncio.gather(*tasks)

    # Load existing ledger
    ledger_path = coreason_dir / "capability_ledger.json"
    lock_path = coreason_dir / "capability_ledger.json.lock"

    with FileLock(lock_path, timeout=10):
        ledger_data: dict[str, str] = {}
        if ledger_path.exists():
            try:
                with ledger_path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        ledger_data.update({str(k): str(v) for k, v in loaded.items()})
            except (json.JSONDecodeError, IOError):
                ledger_data = {}

        # 3. Store the hash using target path as key
        for rel_path_str, file_hash in results:
            ledger_data[rel_path_str] = file_hash

        # 4. Register the hash into .coreason/capability_ledger.json
        with ledger_path.open("w", encoding="utf-8") as f:
            json.dump(ledger_data, f, indent=4)
