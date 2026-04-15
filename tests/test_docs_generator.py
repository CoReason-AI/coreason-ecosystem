# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import json
from pathlib import Path

import pytest

from coreason_ecosystem.docs_generator import generate_dynamic_docs


def test_generate_dynamic_docs_schema_exists(tmp_path: Path) -> None:
    """Test docs generation when the ontology schema exists."""
    schema = {"title": "Test Ontology", "description": "A test schema"}
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_text(json.dumps(schema))

    output_dir = tmp_path / "docs_output"

    generate_dynamic_docs(schema_path=schema_path, output_dir=output_dir)

    assert output_dir.exists()
    index_path = output_dir / "index.md"
    assert index_path.exists()
    content = index_path.read_text()
    assert "Test Ontology" in content
    assert "Auto-generated" in content


def test_generate_dynamic_docs_schema_missing(tmp_path: Path) -> None:
    """Test docs generation when the ontology schema does not exist."""
    schema_path = tmp_path / "nonexistent.schema.json"
    output_dir = tmp_path / "docs_output"

    generate_dynamic_docs(schema_path=schema_path, output_dir=output_dir)

    # Should create output_dir but not index.md since schema is missing
    assert output_dir.exists()
    assert not (output_dir / "index.md").exists()


def test_generate_dynamic_docs_defaults(tmp_path: Path, monkeypatch: "pytest.MonkeyPatch") -> None:
    """Test docs generation with default paths (CWD-based)."""
    monkeypatch.chdir(tmp_path)

    schema = {"title": "Default Ontology"}
    (tmp_path / "coreason_ontology.schema.json").write_text(json.dumps(schema))

    generate_dynamic_docs()

    docs_dir = tmp_path / "docs"
    assert docs_dir.exists()
    assert (docs_dir / "index.md").exists()
    content = (docs_dir / "index.md").read_text()
    assert "Default Ontology" in content


def test_generate_dynamic_docs_no_title(tmp_path: Path) -> None:
    """Test docs generation when schema has no title field."""
    schema = {"description": "No title here"}
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))

    output_dir = tmp_path / "docs_output"
    generate_dynamic_docs(schema_path=schema_path, output_dir=output_dir)

    content = (output_dir / "index.md").read_text()
    assert "CoReason Ontology" in content  # fallback title
