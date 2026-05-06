from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import typer

from coreason_ecosystem.orchestration.sync import (
    detect_and_heal_drift,
    execute_sync,
    establish_federated_link,
)
from coreason_manifest.spec.ontology import FederatedSecurityMacroManifest


@pytest.mark.asyncio
async def test_detect_and_heal_drift() -> None:
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        proc_prune = AsyncMock()
        proc_prune.communicate.return_value = (b"", b"")
        proc_ls = AsyncMock()
        proc_ls.communicate.return_value = (
            b"coreason-1\ncoreason-default\nother-net\n",
            b"",
        )
        proc_rm = AsyncMock()
        proc_rm.communicate.return_value = (b"", b"")

        mock_exec.side_effect = [proc_prune, proc_ls, proc_rm]

        await detect_and_heal_drift("docker")

        assert mock_exec.call_count == 3
        # prune
        assert mock_exec.mock_calls[0].args == ("docker", "network", "prune", "-f")
        # ls
        assert mock_exec.mock_calls[1].args == (
            "docker",
            "network",
            "ls",
            "--format",
            "{{.Name}}",
        )
        # rm
        assert mock_exec.mock_calls[2].args == ("docker", "network", "rm", "coreason-1")


@pytest.mark.asyncio
async def test_execute_sync_success(tmp_path: Path) -> None:
    with (
        patch("coreason_ecosystem.orchestration.sync.Path.cwd", return_value=tmp_path),
        patch(
            "coreason_ecosystem.orchestration.sync.detect_and_heal_drift",
            new_callable=AsyncMock,
        ) as mock_drift,
        patch(
            "coreason_ecosystem.orchestration.sync.execute_build",
            new_callable=AsyncMock,
        ) as mock_build,
        patch(
            "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
            new_callable=AsyncMock,
        ) as mock_calc,
        patch(
            "coreason_ecosystem.orchestration.sync.write_registry_lock"
        ) as mock_write,
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch("coreason_ecosystem.orchestration.sync.Path.exists", return_value=True),
    ):
        mock_calc.return_value = "fake_root_hash"

        proc_up = AsyncMock()
        proc_up.communicate.return_value = (b"", b"")
        proc_up.returncode = 0
        mock_exec.return_value = proc_up

        await execute_sync()

        mock_drift.assert_awaited_once()
        assert (tmp_path / "coreason_ontology.schema.json").exists()
        mock_build.assert_awaited_once()
        mock_calc.assert_awaited_once()
        mock_write.assert_called_once()
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_execute_sync_missing_compose(tmp_path: Path) -> None:
    with (
        patch("coreason_ecosystem.orchestration.sync.Path.cwd", return_value=tmp_path),
        patch(
            "coreason_ecosystem.orchestration.sync.detect_and_heal_drift",
            new_callable=AsyncMock,
        ),
        patch(
            "coreason_ecosystem.orchestration.sync.execute_build",
            new_callable=AsyncMock,
        ),
        patch(
            "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
            new_callable=AsyncMock,
        ),
        patch("coreason_ecosystem.orchestration.sync.write_registry_lock"),
        patch("coreason_ecosystem.orchestration.sync.Path.exists", return_value=False),
    ):
        with pytest.raises(typer.Exit) as exc:
            await execute_sync()
        assert exc.value.exit_code == 1


@pytest.mark.asyncio
async def test_execute_sync_docker_failure(tmp_path: Path) -> None:
    with (
        patch("coreason_ecosystem.orchestration.sync.Path.cwd", return_value=tmp_path),
        patch(
            "coreason_ecosystem.orchestration.sync.detect_and_heal_drift",
            new_callable=AsyncMock,
        ),
        patch(
            "coreason_ecosystem.orchestration.sync.execute_build",
            new_callable=AsyncMock,
        ),
        patch(
            "coreason_ecosystem.orchestration.sync.calculate_epistemic_root",
            new_callable=AsyncMock,
        ),
        patch("coreason_ecosystem.orchestration.sync.write_registry_lock"),
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch("coreason_ecosystem.orchestration.sync.Path.exists", return_value=True),
    ):
        proc_up = AsyncMock()
        proc_up.communicate.return_value = (b"", b"docker error")
        proc_up.returncode = 1
        mock_exec.return_value = proc_up

        with pytest.raises(typer.Exit) as exc:
            await execute_sync()
        assert exc.value.exit_code == 1


@pytest.mark.asyncio
async def test_establish_federated_link() -> None:
    manifest = FederatedSecurityMacroManifest.model_construct(
        target_endpoint_uri="http://example.com",
        required_clearance="PUBLIC",  # type: ignore[arg-type]
        max_liability_budget=100.0,  # type: ignore[arg-type]
    )
    with patch(
        "coreason_ecosystem.orchestration.sync.execute_sync", new_callable=AsyncMock
    ) as mock_sync:
        await establish_federated_link(manifest)
        mock_sync.assert_awaited_once()
