import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import typer

from coreason_ecosystem.orchestration.build import compile_and_hash
from coreason_ecosystem.orchestration.init import execute_init
from coreason_ecosystem.orchestration.sync import execute_sync
from coreason_ecosystem.orchestration.up import execute_up, wait_for_port


@pytest.mark.asyncio
async def test_build_path_value_error(tmp_path: Path) -> None:
    # build.py Lines 27-28
    with patch("pathlib.Path.relative_to", side_effect=ValueError):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            test_py = tmp_path / "test.py"
            test_py.write_text("print('test')")

            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            # Force wasm file presence so FileNotFoundError is bypassed
            import hashlib

            safe_name = f"{hashlib.md5(str(test_py.resolve()).encode(), usedforsecurity=False).hexdigest()[:8]}_{test_py.with_suffix('.wasm').name}"
            (bin_dir / safe_name).touch()

            res_path, res_hash = await compile_and_hash(test_py, bin_dir)
            assert res_path == str(test_py.resolve())


@pytest.mark.asyncio
async def test_build_rust_path(tmp_path: Path) -> None:
    # build.py Lines 49-67 and 97-121
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        pkg_dir = tmp_path / "deep" / "my-rust-crate"
        pkg_dir.mkdir(parents=True)
        # Put Cargo.toml in the parent to force cargo_dir = cargo_dir.parent loop
        cargo_toml = pkg_dir.parent / "Cargo.toml"
        cargo_toml.write_text("hello")

        test_rs = pkg_dir / "test.rs"
        test_rs.write_text("fn main() {}")

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        # Build fake release WASM NOT using the exact stem name, so fallback glob triggers
        release_path = pkg_dir.parent / "target" / "wasm32-wasip1" / "release"
        release_path.mkdir(parents=True)
        (release_path / "other_name.wasm").write_bytes(b"mock_rust")

        rel_path, res_hash = await compile_and_hash(test_rs, bin_dir)
        assert res_hash is not None


@pytest.mark.asyncio
async def test_build_rust_missing_wasm(tmp_path: Path) -> None:
    # build.py Lines 118-121
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        pkg_dir = tmp_path / "my-crate"
        pkg_dir.mkdir()
        (pkg_dir / "Cargo.toml").write_text("hello")
        test_rs = pkg_dir / "test.rs"
        test_rs.touch()

        with pytest.raises(typer.Exit):
            await compile_and_hash(test_rs, tmp_path / "bin")


@pytest.mark.asyncio
async def test_build_go_path(tmp_path: Path) -> None:
    # build.py Lines 68-78
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        test_go = tmp_path / "test.go"
        test_go.write_text("package main")

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        import hashlib

        safe_name = f"{hashlib.md5(str(test_go.resolve()).encode(), usedforsecurity=False).hexdigest()[:8]}_{test_go.with_suffix('.wasm').name}"
        (bin_dir / safe_name).write_bytes(b"mock_go")

        rel_path, res_hash = await compile_and_hash(test_go, bin_dir)
        assert res_hash is not None


@pytest.mark.asyncio
async def test_build_unsupported_type(tmp_path: Path) -> None:
    # build.py Lines 80
    test_txt = tmp_path / "test.txt"
    test_txt.touch()
    with pytest.raises(ValueError, match="Unsupported file type"):
        await compile_and_hash(test_txt, tmp_path / "bin")


@pytest.mark.asyncio
async def test_init_rust_go_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # init.py Lines 71-108, 112-148, 164-167
    monkeypatch.chdir(tmp_path)
    # Happy path version resolution line 165
    await execute_init("test_happy", lang="python")

    import importlib.metadata

    with patch(
        "importlib.metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError,
    ):
        await execute_init("test_rust", lang="rust")
        await execute_init("test_go", lang="go")
        await execute_init("test_py", lang="hello")

    assert (tmp_path / "test_rust" / "Cargo.toml").exists()
    assert (tmp_path / "test_go" / "go.mod").exists()


@pytest.mark.asyncio
async def test_sync_compose_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # sync.py Lines 63-66 => missing compose.yaml throws Exit(1)
    # 89-92 => process.returncode != 0
    monkeypatch.chdir(tmp_path)

    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(typer.Exit):
            await execute_sync()

    infra_dir = tmp_path / "infrastructure" / "local"
    infra_dir.mkdir(parents=True)
    (infra_dir / "compose.yaml").touch()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"error")
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc

        with pytest.raises(typer.Exit):
            await execute_sync()


@pytest.mark.asyncio
async def test_up_wait_for_port() -> None:
    # up.py test wait_for_port execution exceptions
    with patch("asyncio.open_connection", side_effect=Exception("network down")):
        with pytest.raises(TimeoutError):
            await wait_for_port(8000, timeout=1.0)
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        with pytest.raises(TimeoutError):
            await wait_for_port(8000, timeout=1.0)
    with (
        patch("asyncio.wait_for") as wait_for_mock,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_writer = AsyncMock()
        wait_for_mock.return_value = (AsyncMock(), mock_writer)
        await wait_for_port(8000, timeout=1.0)
        mock_writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_up_timeout_fallbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # up.py Lines 87-93, 124-130, 171-177
    monkeypatch.chdir(tmp_path)

    infra_dir = tmp_path / "infrastructure" / "local"
    infra_dir.mkdir(parents=True)
    (infra_dir / "compose.yaml").touch()

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        with patch("asyncio.sleep", AsyncMock()):
            # Test Postgres timeout
            with patch(
                "coreason_ecosystem.orchestration.up.wait_for_postgres",
                side_effect=TimeoutError("PG fails"),
            ):
                with pytest.raises(typer.Exit):
                    await execute_up()

        with patch("asyncio.sleep", AsyncMock()):
            # Test Temporal timeout by letting Postgres pass once
            with (
                patch("coreason_ecosystem.orchestration.up.wait_for_postgres"),
                patch(
                    "coreason_ecosystem.orchestration.up.wait_for_temporal",
                    side_effect=TimeoutError("Temporal fails"),
                ),
            ):
                with pytest.raises(typer.Exit):
                    with patch("coreason_ecosystem.orchestration.up.Progress"):
                        await execute_up()

        with patch("asyncio.sleep", AsyncMock()):
            # Test Daemon timeout by letting Postgres and Temporal pass but Daemon 8000 fail
            with (
                patch("coreason_ecosystem.orchestration.up.wait_for_postgres"),
                patch("coreason_ecosystem.orchestration.up.wait_for_temporal"),
                patch(
                    "coreason_ecosystem.orchestration.up.wait_for_port",
                    side_effect=TimeoutError("Daemon fails"),
                ),
            ):
                with pytest.raises(typer.Exit):
                    with patch("coreason_ecosystem.orchestration.up.Progress"):
                        await execute_up()
