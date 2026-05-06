import json
from pathlib import Path
from unittest.mock import patch

from coreason_ecosystem.docs_generator import generate_dynamic_docs


def test_generate_dynamic_docs_success(tmp_path: Path) -> None:
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_text(json.dumps({"title": "Custom Test Title"}))
    output_dir = tmp_path / "docs"

    generate_dynamic_docs(schema_path=schema_path, output_dir=output_dir)

    assert output_dir.exists()
    index_md = output_dir / "index.md"
    assert index_md.exists()
    content = index_md.read_text()
    assert "# Custom Test Title" in content


def test_generate_dynamic_docs_defaults_missing_schema(tmp_path: Path) -> None:
    with patch("coreason_ecosystem.docs_generator.Path.cwd", return_value=tmp_path):
        with patch("coreason_ecosystem.docs_generator.logger.warning") as mock_warn:
            generate_dynamic_docs()

            mock_warn.assert_called_once()
            output_dir = tmp_path / "docs"
            assert output_dir.exists()
            assert not (output_dir / "index.md").exists()


def test_generate_dynamic_docs_defaults_with_schema(tmp_path: Path) -> None:
    with patch("coreason_ecosystem.docs_generator.Path.cwd", return_value=tmp_path):
        schema_path = tmp_path / "coreason_ontology.schema.json"
        schema_path.write_text(json.dumps({}))  # No title

        generate_dynamic_docs()

        output_dir = tmp_path / "docs"
        assert output_dir.exists()
        index_md = output_dir / "index.md"
        assert index_md.exists()
        content = index_md.read_text()
        assert "# CoReason Ontology" in content
