import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from coreason_ecosystem.orchestration.isomorphism_probe import execute_oracle_diagnostic

from typing import Any, Optional

class MockResponse:
    def __init__(self, status_code: int, elapsed_seconds: float = 0.1) -> None:
        self.status_code = status_code
        self.elapsed = type('obj', (object,), {'total_seconds': lambda *args, **kwargs: elapsed_seconds})()

class MockAsyncClient:
    def __init__(self, get_responses: Optional[dict[str, Any]] = None, stream_responses: Optional[dict[str, Any]] = None) -> None:
        self.get_responses = get_responses or {}
        self.stream_responses = stream_responses or {}

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def get(self, url: str, **kwargs: Any) -> Any:
        if url in self.get_responses:
            resp = self.get_responses[url]
            if isinstance(resp, Exception):
                raise resp
            return resp
        return MockResponse(200)

    def stream(self, method: str, url: str, **kwargs: Any) -> Any:
        class StreamContext:
            def __init__(self, resp: Any) -> None:
                self.resp = resp
            async def __aenter__(self) -> Any:
                if isinstance(self.resp, Exception):
                    raise self.resp
                return self.resp
            async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
                pass
        
        resp = self.stream_responses.get(url, MockResponse(200))
        return StreamContext(resp)


@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_all_success(tmp_path: Path) -> None:
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    with (
        patch("coreason_ecosystem.orchestration.isomorphism_probe.Path.cwd", return_value=tmp_path),
        patch("httpx.AsyncClient", return_value=MockAsyncClient(
            get_responses={
                "http://localhost:8000/docs": MockResponse(200),
                "http://localhost:8000/api/v1/epistemic/verify": MockResponse(200)
            },
            stream_responses={
                "http://localhost:8000/api/v1/telemetry/stream": MockResponse(200)
            }
        )),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.read_registry_lock", return_value="fake_root"),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.calculate_epistemic_root", new_callable=AsyncMock) as mock_calc,
        patch("coreason_ecosystem.cli.console.print") as mock_print
    ):
        mock_calc.return_value = "fake_root"
        await execute_oracle_diagnostic()
        mock_print.assert_called_once()
        table = mock_print.mock_calls[0].args[0]
        # Should be 4 rows
        assert len(table.rows) == 4

@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_all_failures(tmp_path: Path) -> None:
    with (
        patch("coreason_ecosystem.orchestration.isomorphism_probe.Path.cwd", return_value=tmp_path),
        patch("httpx.AsyncClient", return_value=MockAsyncClient(
            get_responses={
                "http://localhost:8000/docs": httpx.RequestError("error"),
                "http://localhost:8000/api/v1/epistemic/verify": httpx.RequestError("error")
            },
            stream_responses={
                "http://localhost:8000/api/v1/telemetry/stream": httpx.RequestError("error")
            }
        )),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.read_registry_lock", return_value=None),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.calculate_epistemic_root", new_callable=AsyncMock) as mock_calc,
        patch("coreason_ecosystem.cli.console.print") as mock_print
    ):
        # Different root forces local drift
        mock_calc.return_value = "different_root"
        await execute_oracle_diagnostic()
        mock_print.assert_called_once()
        table = mock_print.mock_calls[0].args[0]
        assert len(table.rows) == 4

@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_http_errors(tmp_path: Path) -> None:
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    with (
        patch("coreason_ecosystem.orchestration.isomorphism_probe.Path.cwd", return_value=tmp_path),
        patch("httpx.AsyncClient", return_value=MockAsyncClient(
            get_responses={
                "http://localhost:8000/docs": MockResponse(500),
                "http://localhost:8000/api/v1/epistemic/verify": MockResponse(409)
            },
            stream_responses={
                "http://localhost:8000/api/v1/telemetry/stream": MockResponse(500)
            }
        )),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.read_registry_lock", return_value="fake_root"),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.calculate_epistemic_root", new_callable=AsyncMock) as mock_calc,
        patch("coreason_ecosystem.cli.console.print") as mock_print
    ):
        mock_calc.return_value = "fake_root"
        await execute_oracle_diagnostic()
        mock_print.assert_called_once()
        
@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_epistemic_http_error(tmp_path: Path) -> None:
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    with (
        patch("coreason_ecosystem.orchestration.isomorphism_probe.Path.cwd", return_value=tmp_path),
        patch("httpx.AsyncClient", return_value=MockAsyncClient(
            get_responses={
                "http://localhost:8000/docs": MockResponse(200),
                "http://localhost:8000/api/v1/epistemic/verify": MockResponse(500)
            },
            stream_responses={
                "http://localhost:8000/api/v1/telemetry/stream": MockResponse(200)
            }
        )),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.read_registry_lock", return_value="fake_root"),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.calculate_epistemic_root", new_callable=AsyncMock) as mock_calc,
        patch("coreason_ecosystem.cli.console.print") as mock_print
    ):
        mock_calc.return_value = "fake_root"
        await execute_oracle_diagnostic()
        mock_print.assert_called_once()

@pytest.mark.asyncio
async def test_execute_oracle_diagnostic_epistemic_timeout(tmp_path: Path) -> None:
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"{}")
    
    with (
        patch("coreason_ecosystem.orchestration.isomorphism_probe.Path.cwd", return_value=tmp_path),
        patch("httpx.AsyncClient", return_value=MockAsyncClient(
            get_responses={
                "http://localhost:8000/docs": MockResponse(200),
                "http://localhost:8000/api/v1/epistemic/verify": httpx.TimeoutException("timeout")
            },
            stream_responses={
                "http://localhost:8000/api/v1/telemetry/stream": MockResponse(200)
            }
        )),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.read_registry_lock", return_value="fake_root"),
        patch("coreason_ecosystem.orchestration.isomorphism_probe.calculate_epistemic_root", new_callable=AsyncMock) as mock_calc,
        patch("coreason_ecosystem.cli.console.print") as mock_print
    ):
        mock_calc.return_value = "fake_root"
        await execute_oracle_diagnostic()
        mock_print.assert_called_once()
