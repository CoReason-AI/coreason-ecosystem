# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Epistemic Documentation Generator.

Dynamically parses coreason_ontology.schema.json and generates
static MkDocs/Material documentation portals. Per RULE 2 (Zero-Waste Mandate),
documentation is a mathematical derivative of the codebase, never a manual transcription.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger


def generate_dynamic_docs(
    schema_path: Path | None = None,
    output_dir: Path | None = None,
) -> None:
    """Generate MkDocs documentation from the ontological schema.

    Args:
        schema_path: Path to coreason_ontology.schema.json. Defaults to CWD.
        output_dir: Output directory for generated docs. Defaults to ./docs.
    """
    if schema_path is None:
        schema_path = Path.cwd() / "coreason_ontology.schema.json"

    if output_dir is None:
        output_dir = Path.cwd() / "docs"

    output_dir.mkdir(parents=True, exist_ok=True)

    if not schema_path.exists():
        logger.warning(
            f"Ontology schema not found at {schema_path}. "
            "Run 'coreason sync' to generate it."
        )
        return

    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    # Generate index page from schema metadata
    title = schema.get("title", "CoReason Ontology")
    index_content = f"# {title}\n\nAuto-generated from `coreason_ontology.schema.json`.\n"

    index_path = output_dir / "index.md"
    index_path.write_text(index_content, encoding="utf-8")

    logger.info(f"Documentation generated at {output_dir}")
