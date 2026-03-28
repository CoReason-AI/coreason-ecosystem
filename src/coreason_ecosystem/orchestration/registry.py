# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import hashlib
import importlib.metadata
from pathlib import Path


async def calculate_epistemic_root(project_path: Path) -> str:
    """Calculate the Epistemic Merkle Root."""

    # Component 1 (H_ontology)
    schema_path = project_path / "coreason_ontology.schema.json"
    if schema_path.exists():
        h_ontology = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    else:
        h_ontology = hashlib.sha256(b"").hexdigest()

    # Component 2 (H_env)
    env_str = ""

    # 1. Get the local manifest version (which the CLI has access to)
    try:
        manifest_version = importlib.metadata.version("coreason-manifest")
        env_str += f"coreason-manifest=={manifest_version}\n"
    except importlib.metadata.PackageNotFoundError:
        manifest_version = "unknown"
        env_str += f"coreason-manifest=={manifest_version}\n"

    # 2. The Runtime version must strictly mirror the manifest version in a locked ecosystem
    env_str += f"coreason-runtime=={manifest_version}\n"

    h_env = hashlib.sha256(env_str.encode("utf-8")).hexdigest()

    # Component 3 (H_capabilities)
    ledger_path = project_path / ".coreason" / "capability_ledger.json"
    if ledger_path.exists():
        h_capabilities = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    else:
        h_capabilities = hashlib.sha256(b"{}").hexdigest()

    # The Merkle Root
    combined = h_ontology + h_env + h_capabilities
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def write_registry_lock(project_path: Path, root_hash: str) -> None:
    """Write the registry lock file with the given Merkle root."""
    lock_path = project_path / ".coreason" / "registry.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(root_hash, encoding="utf-8")


def read_registry_lock(project_path: Path) -> str | None:
    """Read the registry lock file and return the Merkle root if it exists."""
    lock_path = project_path / ".coreason" / "registry.lock"
    if lock_path.exists():
        return lock_path.read_text(encoding="utf-8").strip()
    return None
