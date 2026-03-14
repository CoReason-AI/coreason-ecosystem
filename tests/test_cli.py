# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_ecosystem

from click.testing import CliRunner

from coreason_ecosystem.cli import main


def test_cli_execution() -> None:
    """Test that the CLI executes cleanly and proves dependency linkage."""
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0
    assert "CoReason Ecosystem Execution Plane Initialized." in result.output
