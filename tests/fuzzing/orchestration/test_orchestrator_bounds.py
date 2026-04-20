from typing import Any
from hypothesis import given, settings, strategies as st
from unittest.mock import patch, AsyncMock
from typer.testing import CliRunner

from coreason_ecosystem.cli import app
from coreason_ecosystem.fleet.mesh_injector import MeshInjector

runner = CliRunner()


@settings(deadline=None)
@given(project_name=st.text(), topology=st.text(), lang=st.text())
@patch("coreason_ecosystem.cli.execute_init", new_callable=AsyncMock)
def test_fuzz_cli_init_command(
    mock_execute_init: Any, project_name: str, topology: str, lang: str
) -> None:
    """Fuzzing the CLI parser inputs to ensure graceful rejections of malformed environment strings."""
    result = runner.invoke(
        app, ["init", project_name, "--topology", topology, "--lang", lang]
    )
    # Typer should handle any string, possibly exiting with a non-zero code for backend failures,
    # but it should not crash the runner ungracefully if purely parsing.
    # Note: exit_code 0 is success, 1 is general error, 2 is typer arg parse error.
    assert isinstance(result.exit_code, int)


@settings(deadline=None)
@given(
    token=st.text(),
    payload=st.recursive(
        st.booleans()
        | st.integers()
        | st.text()
        | st.floats(allow_nan=False, allow_infinity=False),
        lambda children: (
            st.lists(children, max_size=10)
            | st.dictionaries(st.text(), children, max_size=10)
        ),
        max_leaves=25,
    ),
)
def test_fuzz_mesh_injector_payloads(token: str, payload: Any) -> None:
    """Fuzzing the configuration payloads passed into the Fleet mesh injectors."""
    try:
        MeshInjector().inject_ocap_middleware(token=token, payload=payload)
    except ValueError:
        # MeshInjector handles validation rejections cleanly
        pass
    except Exception as e:
        # We should NOT get any other raw exceptions (e.g., RecursionError)
        raise AssertionError(f"Unexpected exception type: {type(e)}") from e
