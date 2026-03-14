from click.testing import CliRunner

from coreason_ecosystem.cli import main


def test_cli_execution() -> None:
    """Test that the CLI executes cleanly and proves dependency linkage."""
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0
    assert "CoReason Ecosystem Execution Plane Initialized." in result.output
