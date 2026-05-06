import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import typer

from coreason_ecosystem.orchestration.build import (
    compile_and_hash,
    is_mcp_tool,
    execute_build,
)

@pytest.mark.asyncio
async def test_compile_and_hash_py(tmp_path: Path) -> None:
    py_file = tmp_path / "test.py"
    py_file.write_text("print('test')")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_exec.return_value = proc
        
        # mock the read_bytes for the target wasm
        with patch.object(Path, "read_bytes", return_value=b"wasm_content"):
            rel_path, f_hash = await compile_and_hash(py_file, bin_dir)
            assert f_hash == hashlib.sha256(b"wasm_content").hexdigest()
            mock_exec.assert_called_once()
            assert "componentize-py" in mock_exec.mock_calls[0].args

@pytest.mark.asyncio
async def test_compile_and_hash_rs_fallback(tmp_path: Path) -> None:
    cargo_dir = tmp_path / "test_rs_project"
    cargo_dir.mkdir()
    (cargo_dir / "Cargo.toml").write_text("[package]")
    rs_file = cargo_dir / "src" / "main.rs"
    rs_file.parent.mkdir(parents=True)
    rs_file.write_text("fn main() {}")
    
    py_file = tmp_path / "test.py"
    py_file.write_text("print('test')")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    
    with patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"out", b"err"))
        mock_exec.return_value = mock_proc
        
        # We need the fallback `.glob("*.wasm")` logic
        target_wasm = cargo_dir / "target" / "wasm32-wasip1" / "release" / "other_name.wasm"
        target_wasm.parent.mkdir(parents=True, exist_ok=True)
        target_wasm.write_bytes(b"dummy wasm fallback")
        
        rel_path, f_hash = await compile_and_hash(rs_file, bin_dir)
        assert target_wasm.exists()
        # wasm_out_path is named using MD5 of rel_path, verify something was placed in bin_dir
        assert any(bin_dir.glob("*.wasm")), "Expected compiled WASM in bin_dir"

@pytest.mark.asyncio
async def test_compile_and_hash_rs_missing_wasm(tmp_path: Path) -> None:
    cargo_dir = tmp_path / "test_rs_project_err"
    cargo_dir.mkdir()
    (cargo_dir / "Cargo.toml").write_text("[package]")
    rs_file = cargo_dir / "src" / "main.rs"
    rs_file.parent.mkdir()
    rs_file.write_text("fn main() {}")
    
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    
    with patch("coreason_ecosystem.orchestration.build.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"out", b"err"))
        mock_exec.return_value = mock_proc
        
        # Intentionally missing the target wasm file
        with pytest.raises(typer.Exit) as exc_info:
            await compile_and_hash(rs_file, bin_dir)
        assert exc_info.value.exit_code == 1

@pytest.mark.asyncio
async def test_compile_and_hash_rs(tmp_path: Path) -> None:
    cargo_dir = tmp_path / "test_rs_project"
    cargo_dir.mkdir()
    (cargo_dir / "Cargo.toml").write_text("[package]")
    
    # Put rs_file deeper so it triggers the while loop
    rs_file = cargo_dir / "src" / "deep" / "main.rs"
    rs_file.parent.mkdir(parents=True)
    rs_file.write_text("fn main() {}")
    
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    
    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch("shutil.copy2") as mock_copy
    ):
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_exec.return_value = proc
        
        # Create a dummy output wasm file so exists() returns True
        out_wasm_dir = cargo_dir / "target" / "wasm32-wasip1" / "release"
        out_wasm_dir.mkdir(parents=True)
        out_wasm = out_wasm_dir / f"{cargo_dir.name.replace('-', '_')}.wasm"
        out_wasm.touch()
        
        with patch.object(Path, "read_bytes", return_value=b"wasm_content"):
            rel_path, f_hash = await compile_and_hash(rs_file, bin_dir)
            assert f_hash == hashlib.sha256(b"wasm_content").hexdigest()
            mock_exec.assert_called_once()
            assert "cargo" in mock_exec.mock_calls[0].args
            mock_copy.assert_called_once()

@pytest.mark.asyncio
async def test_compile_and_hash_go(tmp_path: Path) -> None:
    go_file = tmp_path / "test.go"
    go_file.write_text("package main")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_exec.return_value = proc
        
        with patch.object(Path, "read_bytes", return_value=b"wasm_content"):
            rel_path, f_hash = await compile_and_hash(go_file, bin_dir)
            assert f_hash == hashlib.sha256(b"wasm_content").hexdigest()
            mock_exec.assert_called_once()
            assert "tinygo" in mock_exec.mock_calls[0].args

@pytest.mark.asyncio
async def test_compile_and_hash_unsupported(tmp_path: Path) -> None:
    unsupported_file = tmp_path / "test.txt"
    unsupported_file.write_text("test")
    bin_dir = tmp_path / "bin"
    
    with pytest.raises(ValueError, match="Unsupported file type"):
        await compile_and_hash(unsupported_file, bin_dir)

@pytest.mark.asyncio
async def test_compile_and_hash_compiler_missing(tmp_path: Path) -> None:
    py_file = tmp_path / "test.py"
    py_file.write_text("print('test')")
    bin_dir = tmp_path / "bin"
    
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        with pytest.raises(typer.Exit) as exc:
            await compile_and_hash(py_file, bin_dir)
        assert exc.value.exit_code == 1

@pytest.mark.asyncio
async def test_compile_and_hash_compile_error(tmp_path: Path) -> None:
    py_file = tmp_path / "test.py"
    py_file.write_text("print('test')")
    bin_dir = tmp_path / "bin"
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"error")
        proc.returncode = 1
        mock_exec.return_value = proc
        
        with pytest.raises(typer.Exit) as exc:
            await compile_and_hash(py_file, bin_dir)
        assert exc.value.exit_code == 1

def test_is_mcp_tool(tmp_path: Path) -> None:
    py_tool = tmp_path / "tool.py"
    py_tool.write_text("import mcp")
    assert is_mcp_tool(py_tool) is True
    
    py_tool2 = tmp_path / "tool2.py"
    py_tool2.write_text("__action_space_urn__ = 'test'")
    assert is_mcp_tool(py_tool2) is True
    
    py_tool3 = tmp_path / "tool3.py"
    py_tool3.write_text("from mcp import foo")
    assert is_mcp_tool(py_tool3) is True
    
    py_not_tool = tmp_path / "not_tool.py"
    py_not_tool.write_text("import os")
    assert is_mcp_tool(py_not_tool) is False
    
    txt_file = tmp_path / "not.txt"
    assert is_mcp_tool(txt_file) is False

    py_not_tool2 = tmp_path / "not_tool2.py"
    py_not_tool2.write_text("import json")
    assert is_mcp_tool(py_not_tool2) is False

    py_not_tool3 = tmp_path / "not_tool3.py"
    py_not_tool3.write_text("from os import path")
    assert is_mcp_tool(py_not_tool3) is False

    py_invalid = tmp_path / "invalid.py"
    py_invalid.write_text("invalid syntax here!!")
    assert is_mcp_tool(py_invalid) is False

@pytest.mark.asyncio
async def test_execute_build_missing_target() -> None:
    with patch("coreason_ecosystem.cli.console.print") as mock_print:
        await execute_build("/nonexistent/path")
        mock_print.assert_called_once()
        assert "does not exist" in mock_print.mock_calls[0].args[0]

@pytest.mark.asyncio
async def test_execute_build_success(tmp_path: Path) -> None:
    target_dir = tmp_path / "project"
    target_dir.mkdir()
    
    cap_dir = target_dir / "src" / "capabilities"
    cap_dir.mkdir(parents=True)
    src_file = cap_dir / "app.py"
    src_file.write_text("print('hello')")
    rs_file = cap_dir / "app.rs"
    rs_file.write_text("fn main() {}")
    go_file = cap_dir / "app.go"
    go_file.write_text("package main")
    
    with (
        patch("coreason_ecosystem.orchestration.build.Path.cwd", return_value=tmp_path),
        patch("coreason_ecosystem.orchestration.build.compile_and_hash", new_callable=AsyncMock) as mock_compile
    ):
        mock_compile.return_value = ("project/src/capabilities/app.py", "fakehash")
        await execute_build(str(target_dir))
        
        assert mock_compile.call_count == 3
        
        ledger_path = tmp_path / ".coreason" / "capability_ledger.json"
        assert ledger_path.exists()
        ledger_data = json.loads(ledger_path.read_text())
        assert ledger_data["project/src/capabilities/app.py"] == "fakehash"

@pytest.mark.asyncio
async def test_execute_build_file_target(tmp_path: Path) -> None:
    src_file = tmp_path / "app.py"
    src_file.write_text("print('hello')")
    
    with (
        patch("coreason_ecosystem.orchestration.build.Path.cwd", return_value=tmp_path),
        patch("coreason_ecosystem.orchestration.build.compile_and_hash", new_callable=AsyncMock) as mock_compile
    ):
        mock_compile.return_value = ("app.py", "fakehash")
        await execute_build(str(src_file))
        mock_compile.assert_awaited_once()

@pytest.mark.asyncio
async def test_execute_build_corrupt_ledger(tmp_path: Path) -> None:
    target_dir = tmp_path / "project"
    target_dir.mkdir()
    cap_dir = target_dir / "src" / "capabilities"
    cap_dir.mkdir(parents=True)
    src_file = cap_dir / "app.py"
    src_file.write_text("print('hello')")
    
    with (
        patch("coreason_ecosystem.orchestration.build.Path.cwd", return_value=tmp_path),
        patch("coreason_ecosystem.orchestration.build.compile_and_hash", new_callable=AsyncMock) as mock_compile
    ):
        mock_compile.return_value = ("project/src/capabilities/app.py", "fakehash")
        coreason_dir = tmp_path / ".coreason"
        coreason_dir.mkdir()
        (coreason_dir / "capability_ledger.json").write_text("invalid json")
        
        await execute_build(str(target_dir))
        assert mock_compile.call_count == 1
        
        ledger_data = json.loads((coreason_dir / "capability_ledger.json").read_text())
        assert ledger_data["project/src/capabilities/app.py"] == "fakehash"

@pytest.mark.asyncio
async def test_execute_build_no_capabilities(tmp_path: Path) -> None:
    target_dir = tmp_path / "project"
    target_dir.mkdir()
    # Create an MCP tool which should be filtered out
    mcp_file = target_dir / "tool.py"
    mcp_file.write_text("import mcp")
    
    with patch("coreason_ecosystem.cli.console.print") as mock_print:
        await execute_build(str(target_dir))
        mock_print.assert_called_once()
        assert "No capabilities found to build" in mock_print.mock_calls[0].args[0]
