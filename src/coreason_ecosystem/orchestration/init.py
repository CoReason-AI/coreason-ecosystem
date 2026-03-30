# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import importlib.metadata
import asyncio
import json
from pathlib import Path


async def execute_init(project_name: str, topology: str = "base") -> None:
    """Synthesize a mathematically verified Swarm workspace."""
    if "/" in project_name or "\\" in project_name:
        raise ValueError("Project name cannot contain path separators")

    project_path = Path(project_name).resolve()
    cwd = Path.cwd().resolve()
    if not project_path.is_relative_to(cwd) or project_path == cwd:
        raise ValueError(
            "Project path must be a subdirectory of the current working directory"
        )

    project_path.mkdir(parents=True, exist_ok=True)

    # 1. Directory Genesis
    package_name = project_name.replace("-", "_")
    package_dir = project_path / "src" / package_name
    (package_dir / "agents").mkdir(parents=True, exist_ok=True)
    (package_dir / "agents" / "__init__.py").touch()
    (package_dir / "capabilities").mkdir(parents=True, exist_ok=True)
    (package_dir / "capabilities" / "__init__.py").touch()
    (package_dir / "intents").mkdir(parents=True, exist_ok=True)
    (package_dir / "intents" / "__init__.py").touch()
    (package_dir / "__init__.py").touch()

    # 2. Dependency Locking
    def get_version(pkg_name: str) -> str:
        try:
            return importlib.metadata.version(pkg_name)
        except importlib.metadata.PackageNotFoundError:
            return "0.1.0"  # Fallback

    runtime_version = get_version("coreason-runtime")
    manifest_version = get_version("coreason-manifest")
    ecosystem_version = get_version("coreason-ecosystem")

    pyproject_toml_content = f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{project_name}"
version = "0.1.0"
description = "Autopoietically generated CoReason Swarm Workspace"
requires-python = ">=3.14"
dependencies = [
    "coreason-runtime>={runtime_version}",
    "coreason-manifest>={manifest_version}",
    "componentize-py<0.14",
    "python-pdk"
]

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]

[dependency-groups]
dev = [
    "pre-commit"
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]

[tool.uv.sources]
coreason-ecosystem = {{ path = ".." }}
python-pdk = {{ git = "https://github.com/extism/python-pdk" }}
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
    cap_dir = package_dir / "capabilities"
    cap_template = """# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import json
import sys

class ExampleWorld:
    def main(self) -> None:
        \"\"\"Entry point for the WASM capability.\"\"\"
        # Capability logic goes here
        pass
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

    # 7. WASM Interface (WIT)
    wit_dir = project_path / "wit"
    wit_dir.mkdir(parents=True, exist_ok=True)
    wit_content = """package coreason:capability;

world example-world {
    export main: func();
}
"""
    (wit_dir / "world.wit").write_text(wit_content)

    process = await asyncio.create_subprocess_exec("git", "init", cwd=str(project_path))
    await process.communicate()
