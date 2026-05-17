# Copyright (c) 2026 CoReason, Inc.
import pytest
from typer.testing import CliRunner
import importlib.metadata
from coreason_ecosystem.cli import app, version_callback
import typer

runner = CliRunner()


class FakeMetadata:
    """Fake metadata for physical substrate testing."""

    @staticmethod
    def version(package: str) -> str:
        if package == "coreason-ecosystem":
            return "1.0.0"
        raise importlib.metadata.PackageNotFoundError


def test_version_callback_true(monkeypatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", FakeMetadata.version)
    with pytest.raises(typer.Exit):
        version_callback(True)


def test_version_callback_package_not_found(monkeypatch) -> None:
    def mock_version(package: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", mock_version)
    with pytest.raises(typer.Exit):
        version_callback(True)


def test_version_callback_false() -> None:
    # Should do nothing
    version_callback(False)


class CLIState:
    def __init__(self):
        self.up_called = False
        self.doctor_called = False
        self.sync_called = False
        self.docs_called = False


@pytest.fixture
def cli_state(monkeypatch):
    state = CLIState()

    async def fake_up():
        state.up_called = True

    async def fake_doctor():
        state.doctor_called = True

    async def fake_sync():
        state.sync_called = True

    def fake_docs(*args, **kwargs):
        state.docs_called = True

    import coreason_ecosystem.cli as cli_module
    import coreason_ecosystem.docs_generator as docs_module

    monkeypatch.setattr(cli_module, "execute_up", fake_up)
    monkeypatch.setattr(cli_module, "execute_oracle_diagnostic", fake_doctor)
    monkeypatch.setattr(cli_module, "execute_sync", fake_sync)
    monkeypatch.setattr(docs_module, "generate_dynamic_docs", fake_docs)

    return state


def test_cli_up(cli_state) -> None:
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert cli_state.up_called


def test_cli_doctor(cli_state) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert cli_state.doctor_called


def test_cli_sync(cli_state) -> None:
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert cli_state.sync_called


def test_cli_build_docs(cli_state) -> None:
    result = runner.invoke(app, ["docs", "build"])
    assert result.exit_code == 0
    assert cli_state.docs_called


def test_cli_build_docs_failure(monkeypatch, cli_state) -> None:
    def fail_docs(*args, **kwargs):
        raise Exception("Docs failed")

    import coreason_ecosystem.docs_generator as docs_module

    monkeypatch.setattr(docs_module, "generate_dynamic_docs", fail_docs)

    result = runner.invoke(app, ["docs", "build"])
    assert result.exit_code == 0  # Catches exception


def test_cli_main(monkeypatch) -> None:
    called = False

    def mock_app(*args, **kwargs):
        nonlocal called
        called = True

    import coreason_ecosystem.cli as cli_module

    monkeypatch.setattr(cli_module, "app", mock_app)

    from coreason_ecosystem.cli import main

    main()
    assert called
