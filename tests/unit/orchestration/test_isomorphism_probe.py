import os
import json
import asyncio
from pathlib import Path
import pytest
import httpx

from coreason_ecosystem.orchestration.isomorphism_probe import execute_oracle_diagnostic
from coreason_ecosystem.orchestration.registry import calculate_epistemic_root

def create_mock_asgi_app(
    docs_status=200,
    verify_status=200,
    docs_exc=None,
    verify_exc=None,
    stream_exc=None,
):
    async def mock_asgi_app(scope, receive, send):
        if scope["type"] != "http":
            return
            
        path = scope["path"]
        headers = {k.decode("latin1"): v.decode("latin1") for k, v in scope.get("headers", [])}
        
        status = 200
        body = b"OK"
        
        if path == "/docs":
            if docs_exc:
                raise docs_exc
            status = docs_status
        elif path == "/api/v1/telemetry/stream":
            if stream_exc:
                raise stream_exc
        elif path == "/api/v1/epistemic/verify":
            if verify_exc:
                raise verify_exc
            status = verify_status
        else:
            status = 404
            body = b"Not Found"

        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
    return mock_asgi_app


@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_all_success(tmp_path: Path, capsys, monkeypatch):
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    monkeypatch.chdir(tmp_path)
    current_root = await calculate_epistemic_root(tmp_path)
    
    coreason_dir = tmp_path / ".coreason"
    coreason_dir.mkdir(parents=True, exist_ok=True)
    lock_path = coreason_dir / "registry.lock"
    lock_path.write_text(json.dumps({"epistemic_root": current_root}))
    
    transport = httpx.ASGITransport(app=create_mock_asgi_app())
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
    
    await execute_oracle_diagnostic(client=client)
    
    captured = capsys.readouterr()
    assert "Ontological Isomorphism Diagnostic" in captured.out
    assert "✓ ALIVE" in captured.out
    assert "✓ STREAMING" in captured.out
    assert "✓ SYNCED" in captured.out
    assert "✓ ALIGNED" in captured.out


@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_all_failures(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    # Missing schema, missing lock
    # Force network exceptions
    transport = httpx.ASGITransport(
        app=create_mock_asgi_app(
            docs_exc=httpx.RequestError("error"),
            stream_exc=httpx.RequestError("error"),
            verify_exc=httpx.RequestError("error")
        )
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
    
    await execute_oracle_diagnostic(client=client)
    
    captured = capsys.readouterr()
    assert "✗ OFFLINE" in captured.out
    assert "✗ TIMEOUT/OFFLINE" in captured.out
    assert "✗ MISSING" in captured.out
    assert "✗ LOCAL DRIFT DETECTED" in captured.out


@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_http_errors(tmp_path: Path, capsys, monkeypatch):
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    monkeypatch.chdir(tmp_path)
    current_root = await calculate_epistemic_root(tmp_path)
    
    coreason_dir = tmp_path / ".coreason"
    coreason_dir.mkdir(parents=True, exist_ok=True)
    lock_path = coreason_dir / "registry.lock"
    lock_path.write_text(json.dumps({"epistemic_root": current_root}))
    
    transport = httpx.ASGITransport(
        app=create_mock_asgi_app(docs_status=500, verify_status=409)
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
    
    await execute_oracle_diagnostic(client=client)
    
    captured = capsys.readouterr()
    assert "✗ ERROR 500" in captured.out
    assert "✗ DRIFT DETECTED" in captured.out


@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_epistemic_http_error(tmp_path: Path, capsys, monkeypatch):
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    monkeypatch.chdir(tmp_path)
    current_root = await calculate_epistemic_root(tmp_path)
    
    coreason_dir = tmp_path / ".coreason"
    coreason_dir.mkdir(parents=True, exist_ok=True)
    lock_path = coreason_dir / "registry.lock"
    lock_path.write_text(json.dumps({"epistemic_root": current_root}))
    
    transport = httpx.ASGITransport(
        app=create_mock_asgi_app(docs_status=200, verify_status=500)
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
    
    await execute_oracle_diagnostic(client=client)
    
    captured = capsys.readouterr()
    assert "⚠ HTTP 500" in captured.out


@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_epistemic_timeout(tmp_path: Path, capsys, monkeypatch):
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    monkeypatch.chdir(tmp_path)
    current_root = await calculate_epistemic_root(tmp_path)
    
    coreason_dir = tmp_path / ".coreason"
    coreason_dir.mkdir(parents=True, exist_ok=True)
    lock_path = coreason_dir / "registry.lock"
    lock_path.write_text(json.dumps({"epistemic_root": current_root}))
    
    transport = httpx.ASGITransport(
        app=create_mock_asgi_app(verify_exc=httpx.TimeoutException("timeout"))
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:8000")
    
    await execute_oracle_diagnostic(client=client)
    
    captured = capsys.readouterr()
    assert "⚠ UNREACHABLE" in captured.out
