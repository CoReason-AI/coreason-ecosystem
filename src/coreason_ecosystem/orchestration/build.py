# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import ast
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

    safe_name = f"{hashlib.md5(str(rel_path).encode(), usedforsecurity=False).hexdigest()[:8]}_{file_path.with_suffix('.wasm').name}"  # nosec B324
    wasm_out_path = bin_dir / safe_name
    module_name = ".".join(rel_path.with_suffix("").parts)

    try:
        if file_path.suffix == ".py":
            compile_proc = await asyncio.create_subprocess_exec(
                "componentize-py",
                "-d",
                "wit",
                "-w",
                "example-world",
                "componentize",
                module_name,
                "-o",
                str(wasm_out_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        elif file_path.suffix == ".rs":
            cargo_dir = file_path.parent
            while (
                not (cargo_dir / "Cargo.toml").exists()
                and cargo_dir != cargo_dir.parent
            ):
                cargo_dir = cargo_dir.parent

            compile_proc = await asyncio.create_subprocess_exec(
                "cargo",
                "component",
                "build",
                "--release",
                "--target",
                "wasm32-wasip1",
                cwd=str(cargo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        elif file_path.suffix == ".go":
            compile_proc = await asyncio.create_subprocess_exec(
                "tinygo",
                "build",
                "-target=wasi",
                "-o",
                str(wasm_out_path),
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")

        stdout, stderr = await compile_proc.communicate()
    except FileNotFoundError:
        console.print(
            "[bold red]✗ Fatal Error: Missing compiler for toolchain.[/bold red]"
        )
        raise typer.Exit(1)

    if compile_proc.returncode != 0:
        console.print(f"[bold red]Error compiling {file_path}:[/bold red]")
        console.print(stderr.decode("utf-8", errors="replace"))
        raise typer.Exit(1)

    import shutil

    if file_path.suffix == ".rs":
        cargo_dir = file_path.parent
        while not (cargo_dir / "Cargo.toml").exists() and cargo_dir != cargo_dir.parent:
            cargo_dir = cargo_dir.parent

        # Attempt to locate the exact wasm output based on the directory name
        expected_stem = cargo_dir.name.replace("-", "_")
        target_wasm = (
            cargo_dir / "target" / "wasm32-wasip1" / "release" / f"{expected_stem}.wasm"
        )

        if not target_wasm.exists():
            # Fallback to recursively searching the release folder just in case the crate name differs
            found = list(
                (cargo_dir / "target" / "wasm32-wasip1" / "release").glob("*.wasm")
            )
            if found:
                target_wasm = found[0]

        if target_wasm.exists():
            shutil.copy2(target_wasm, wasm_out_path)
        else:
            console.print(
                f"[bold red]Error: Could not locate compiled WASM for {file_path}[/bold red]\nExpected at: {target_wasm}"
            )
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


def is_mcp_tool(file_path: Path) -> bool:
    """Zero-Trust Passive Projection (AST parsing) to detect MCP tools."""
    if file_path.suffix != ".py":
        return False
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if getattr(target, "id", None) == "__action_space_urn__":
                        return True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("mcp.") or alias.name == "mcp":
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module.startswith("mcp.") or node.module == "mcp"
                ):
                    return True
    except Exception:
        pass  # nosec B110
    return False


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
            files_to_build: list[Path] = []
            files_to_build.extend(cap_dir.rglob("*.py"))
            files_to_build.extend(cap_dir.rglob("*.rs"))
            files_to_build.extend(cap_dir.rglob("*.go"))
        else:
            files_to_build = []
            files_to_build.extend(target.rglob("*.py"))
            files_to_build.extend(target.rglob("*.rs"))
            files_to_build.extend(target.rglob("*.go"))
    else:
        files_to_build = [target]
    # Filter out generated files, virtual environments, tests, and ecosystem internals
    EXCLUDE_DIRS = {"target", ".venv", "tests", "infrastructure", "coreason_ecosystem"}
    files_to_build = [
        f
        for f in files_to_build
        if not set(f.parts).intersection(EXCLUDE_DIRS) and not is_mcp_tool(f)
    ]

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
            except json.JSONDecodeError, IOError:
                ledger_data = {}

        # 3. Store the hash using target path as key
        for rel_path_str, file_hash in results:
            ledger_data[rel_path_str] = file_hash

        # 4. Register the hash into .coreason/capability_ledger.json
        with ledger_path.open("w", encoding="utf-8") as f:
            json.dump(ledger_data, f, indent=4)
