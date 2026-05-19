import subprocess
import sys


def test_main_execution() -> None:
    # Execute the CLI physically to satisfy Anti-Mocking "Real Test" Directive
    result = subprocess.run(
        [sys.executable, "-m", "coreason_ecosystem", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Usage: coreason" in result.stdout
    assert result.returncode == 0
