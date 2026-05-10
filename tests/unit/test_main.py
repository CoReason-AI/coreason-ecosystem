from typing import Any
import runpy
import sys
from unittest.mock import patch


def test_main_execution() -> None:
    with patch("coreason_ecosystem.cli.app") as mock_app:
        with patch.object(sys, "argv", ["coreason"]):
            runpy.run_module("coreason_ecosystem.__main__", run_name="__main__")
            mock_app.assert_called_once_with(prog_name="coreason")
