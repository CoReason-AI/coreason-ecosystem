# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from coreason_ecosystem.cli import app

runner = CliRunner()


@patch("coreason_ecosystem.docs_generator.generate_dynamic_docs")
def test_docs_build_success(mock_generate: Any) -> None:
    """Test the docs build subcommand succeeds."""
    result = runner.invoke(app, ["docs", "build"])
    assert result.exit_code == 0
    mock_generate.assert_called_once()


@patch(
    "coreason_ecosystem.docs_generator.generate_dynamic_docs",
    side_effect=Exception("Schema parse error"),
)
def test_docs_build_failure(mock_generate: Any) -> None:
    """Test the docs build subcommand handles exceptions gracefully."""
    result = runner.invoke(app, ["docs", "build"])
    assert result.exit_code == 0
    assert "Documentation Pipeline Failed" in result.stdout
    assert "Schema parse error" in result.stdout
