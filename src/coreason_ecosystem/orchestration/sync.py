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
from coreason_ecosystem.orchestration.build import execute_build
from coreason_ecosystem.orchestration.registry import (
    calculate_epistemic_root,
    write_registry_lock,
)
from coreason_manifest.spec.ontology import FederatedSecurityMacroManifest
from loguru import logger


import shutil


async def detect_and_heal_drift(docker_bin: str) -> None:
    """Automated Drift Teardown sequence.

    Actively detects network drift by forcefully pruning unused Docker networks
    and systematically tearing down stale coreason-* bridge network segments.
    This aggressive teardown enforces structural topology bounds before the
    subsequent sync rebuilds the deterministic eBPF lattice.
    """
    proc = await asyncio.create_subprocess_exec(
        docker_bin,
        "network",
        "prune",
        "-f",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    await proc.communicate()

    proc = await asyncio.create_subprocess_exec(
        docker_bin,
        "network",
        "ls",
        "--format",
        "{{.Name}}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    networks = stdout.decode().splitlines()
    for net in networks:
        if net.startswith("coreason") and net != "coreason-default":
            rm_proc = await asyncio.create_subprocess_exec(
                docker_bin,
                "network",
                "rm",
                net,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await rm_proc.communicate()
async def generate_runtime_mcp_config() -> None:
    """Passively scan ASTs across repos to dynamically compile mcp_servers.json."""
    import ast
    import json
    import os
    import sys
    
    workspace_root_env = os.environ.get("COREASON_WORKSPACE_ROOT")
    workspace_root = Path(workspace_root_env) if workspace_root_env else Path(__file__).resolve().parents[4]
    
    runtime_path = os.environ.get("COREASON_RUNTIME_PATH")
    mcp_servers_path = Path(runtime_path) / "mcp_servers.json" if runtime_path else workspace_root / "coreason-runtime" / "mcp_servers.json"
    
    if mcp_servers_path.exists():
        with mcp_servers_path.open("r", encoding="utf-8") as f:
            servers = json.load(f)
    else:
        servers = {}

    urn_path_env = os.environ.get("COREASON_URN_AUTHORITY_PATH")
    meta_path_env = os.environ.get("COREASON_META_ENGINEERING_PATH")
    
    urn_auth_dir = Path(urn_path_env) if urn_path_env else workspace_root / "coreason-urn-authority"
    meta_eng_dir = Path(meta_path_env) if meta_path_env else workspace_root / "coreason-meta-engineering"

    scan_dirs = [
        urn_auth_dir / "assets",
        meta_eng_dir / "src"
    ]
    
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if "tests" in py_file.parts:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except Exception:
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__action_space_urn__":
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                urn = node.value.value
                                parts = urn.split(":")
                                alias = parts[4] if len(parts) >= 5 else parts[-1]
                                
                                project_dir = str(urn_auth_dir) if str(urn_auth_dir) in str(py_file) else str(meta_eng_dir)
                                
                                is_dev = os.environ.get("COREASON_DEV_MODE") == "1"
                                is_meta_engineering = str(meta_eng_dir) in str(py_file)
                                
                                if is_meta_engineering:
                                    # Meta-engineering is a pip-installed package with a registered
                                    # CLI entry point. Use `coreason-meta-mcp` directly.
                                    if is_dev:
                                        cmd = "uv"
                                        cmd_args = ["run", "coreason-meta-mcp"]
                                    else:
                                        cmd = sys.executable
                                        cmd_args = ["-m", "coreason_meta_engineering.mcp_server"]
                                else:
                                    # URN Authority tools are raw scripts on disk.
                                    # They must be invoked by their absolute file path.
                                    if is_dev:
                                        cmd = "uv"
                                        cmd_args = ["run", "--project", project_dir, "python", str(py_file.resolve())]
                                    else:
                                        cmd = sys.executable
                                        cmd_args = [str(py_file.resolve())]
                                
                                servers[alias] = {
                                    "server_cid": urn,
                                    "transport": {
                                        "topology_class": "stdio",
                                        "command": cmd,
                                        "args": cmd_args,
                                        "env_vars": {}
                                    },
                                    "capability_whitelist": {
                                        "authorized_capability_array": [],
                                        "allowed_resources": [],
                                        "allowed_prompts": []
                                    },
                                    "attestation_receipt": {
                                        "presentation_format": "jwt_vc",
                                        "issuer_did": "did:coreason:metaorchestrator",
                                        "cryptographic_proof_blob": "bW9ja19wcm9vZg==",
                                        "authorization_claims": {
                                            "clearance": "RESTRICTED"
                                        }
                                    },
                                    "state_synchronization_optics": []
                                }
                                
    with mcp_servers_path.open("w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2)


async def execute_sync() -> None:
    """Autonomically heal Ontological Drift."""

    project_path = Path.cwd()
    docker_bin = shutil.which("docker") or "docker"

    with Status("[cyan]Detecting Drift...[/cyan]", console=console) as status:
        status.update("[cyan]Executing Automated Drift Teardown...[/cyan]")
        await detect_and_heal_drift(docker_bin)

        status.update("[yellow]Regenerating Ontology...[/yellow]")
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Swarm Ontology",
        }
        schema_path = project_path / "coreason_ontology.schema.json"
        with schema_path.open("w", encoding="utf-8") as f:
            import json

            json.dump(schema, f, indent=4)

        status.update("[magenta]Re-crystallizing Capabilities...[/magenta]")
        await execute_build(str(project_path))
        await generate_runtime_mcp_config()

        # 3. Registry Sync
        status.update("[blue]Syncing Epistemic Registry...[/blue]")
        root_hash = await calculate_epistemic_root(project_path)
        write_registry_lock(project_path, root_hash)

        # 4. Thermodynamic Restart
        status.update("[red]Initiating Thermodynamic Restart...[/red]")
        compose_path = project_path / "infrastructure" / "local" / "compose.yaml"
        if not compose_path.exists():
            import os
            workspace_root_env = os.environ.get("COREASON_WORKSPACE_ROOT")
            workspace_root = Path(workspace_root_env) if workspace_root_env else Path(__file__).resolve().parents[4]
            compose_path = (
                workspace_root
                / "infrastructure"
                / "local"
                / "compose.yaml"
            )
            if not compose_path.exists():
                console.print(
                    "[bold red]Error: Could not locate compose.yaml in workspace or fallback path.[/bold red]"
                )
                raise typer.Exit(1)

        env = os.environ.copy()
        env["EPISTEMIC_MERKLE_ROOT"] = root_hash

        process = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            str(compose_path.resolve()),
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
        _, stderr = await process.communicate()
        if process.returncode != 0:
            console.print(
                f"[bold red]Error starting coreason-runtime:[/bold red]\n[bold red]{stderr.decode('utf-8')}[/bold red]"
            )
            raise typer.Exit(1)

        status.update("[green]Swarm Restored.[/green]")
        console.print("[bold green]✓ Autopoietic Healing Complete[/bold green]")


async def establish_federated_link(manifest: FederatedSecurityMacroManifest) -> None:
    """Establish a federated link based on the macro manifest.

    Executes the synchronization of federated meshes (local healing via execute_sync).
    """
    logger.info(
        f"[Thermodynamic Actuator] Establishing Federated Link with target mesh: {manifest.target_endpoint_uri}"
    )
    await execute_sync()
