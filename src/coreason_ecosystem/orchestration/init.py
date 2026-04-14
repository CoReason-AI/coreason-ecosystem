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
import json
from pathlib import Path


async def execute_init(project_name: str) -> None:
    """Synthesize a mathematically verified Swarm workspace scaffolding."""
    if "/" in project_name or "\\" in project_name:
        raise ValueError("Project name cannot contain path separators")

    project_path = Path(project_name).resolve()
    cwd = Path.cwd().resolve()
    if not project_path.is_relative_to(cwd) or project_path == cwd:
        raise ValueError(
            "Project path must be a subdirectory of the current working directory"
        )

    project_path.mkdir(parents=True, exist_ok=True)

    vscode_dir = project_path / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "coreason.isEpistemicWorkspace": True,
        "coreason.telemetry.meshPort": 8000,
        "editor.formatOnSave": True,
    }
    with (vscode_dir / "settings.json").open("w") as f:
        json.dump(settings, f, indent=4)

    # 1. Directory Genesis
    package_name = project_name.replace("-", "_")
    package_dir = project_path / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").touch()

    # 2. Dependency Locking
    pyproject_toml_content = f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{project_name}"
version = "0.1.0"
description = "Autopoietically generated CoReason Swarm Workspace"
requires-python = ">=3.14"
dependencies = [
    "coreason-runtime",
    "coreason-ecosystem"
]

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]

[dependency-groups]
dev = [
    "pre-commit"
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
"""
    (project_path / "pyproject.toml").write_text(pyproject_toml_content)

    tasks = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "Ignite Swarm",
                "command": "coreason deploy up",
                "type": "shell",
            },
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
        entry: coreason registry audit
        language: system
        pass_filenames: false
"""
    (project_path / ".pre-commit-config.yaml").write_text(pre_commit_config)

    process = await asyncio.create_subprocess_exec("git", "init", cwd=str(project_path))
    await process.communicate()
