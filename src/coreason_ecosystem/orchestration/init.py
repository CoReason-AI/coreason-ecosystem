# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import importlib.metadata
import json
import subprocess
from pathlib import Path


async def execute_init(project_name: str, topology: str = "base") -> None:
    """Synthesize a mathematically verified Swarm workspace."""
    project_path = Path(project_name)
    project_path.mkdir(parents=True, exist_ok=True)

    # 1. Directory Genesis
    (project_path / "src" / "agents").mkdir(parents=True, exist_ok=True)
    (project_path / "src" / "capabilities").mkdir(parents=True, exist_ok=True)
    (project_path / "src" / "intents").mkdir(parents=True, exist_ok=True)

    # 2. Dependency Locking
    try:
        manifest_version = importlib.metadata.version("coreason-manifest")
    except importlib.metadata.PackageNotFoundError:
        manifest_version = "0.1.0"  # Fallback

    pyproject_toml_content = f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{project_name}"
version = "0.1.0"
description = "Autopoietically generated CoReason Swarm Workspace"
dependencies = [
    "coreason-runtime=={manifest_version}",
    "coreason-manifest=={manifest_version}"
]
"""
    (project_path / "pyproject.toml").write_text(pyproject_toml_content)

    # 3. Ontological Seed
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Swarm Ontology",
    }
    with (project_path / "coreason_ontology.schema.json").open("w") as f:
        json.dump(schema, f, indent=4)

    # 4. Topological Routing
    cap_dir = project_path / "src" / "capabilities"
    cap_template = """# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import json
import sys


def main() -> None:
    \"\"\"Entry point for the Extism capability.\"\"\"
    # Capability logic goes here
    pass


if __name__ == "__main__":
    main()
"""
    if topology == "medallion":
        (cap_dir / "bronze_ingest.py").write_text(cap_template)
        (cap_dir / "silver_cleanse.py").write_text(cap_template)
        (cap_dir / "gold_route.py").write_text(cap_template)
    elif topology == "rag":
        (cap_dir / "embed_document.py").write_text(cap_template)
        (cap_dir / "retrieve_context.py").write_text(cap_template)
    else:  # base
        (cap_dir / "example_tool.py").write_text(cap_template)

    # 5. Sensory Cortex Wiring
    vscode_dir = project_path / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)

    settings = {
        "coreason.isEpistemicWorkspace": True,
        "coreason.telemetry.meshPort": 8000,
        "editor.formatOnSave": True,
    }
    with (vscode_dir / "settings.json").open("w") as f:
        json.dump(settings, f, indent=4)

    tasks = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "Crystallize Capabilities",
                "command": "coreason build",
                "type": "shell",
            },
            {"label": "Ignite Swarm", "command": "coreason up", "type": "shell"},
        ],
    }
    with (vscode_dir / "tasks.json").open("w") as f:
        json.dump(tasks, f, indent=4)

    # 6. Local Immunological System
    pre_commit_config = """repos:
  - repo: local
    hooks:
      - id: epistemic-seal-check
        name: Epistemic Seal Check
        entry: coreason build
        language: system
        pass_filenames: false
"""
    (project_path / ".pre-commit-config.yaml").write_text(pre_commit_config)

    subprocess.run(["git", "init"], cwd=str(project_path), check=False)  # noqa: S607
