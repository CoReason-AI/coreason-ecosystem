import asyncio
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from coreason_ecosystem.fleet.pulumi_actuator import ComputeNodeTarget, PulumiActuator
from coreason_manifest.spec.ontology import EscrowPolicy


@pytest.fixture
def tmp_templates_dir_caching(tmp_path: Path) -> Path:
    aws_dir = tmp_path / "aws_spot"
    vast_dir = tmp_path / "vast_ai"
    aws_dir.mkdir(parents=True, exist_ok=True)
    vast_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def driver_caching(tmp_templates_dir_caching: Path) -> PulumiActuator:
    return PulumiActuator(tmp_templates_dir_caching)


@pytest.mark.asyncio
async def test_reconcile_state_caching_hit(driver_caching: PulumiActuator) -> None:
    """Positive test: Second call should return cached result without hitting Pulumi."""
    # First call - cache miss
    with (
        patch(
            "coreason_ecosystem.fleet.pulumi_actuator.auto.LocalWorkspace"
        ) as mock_workspace,
        patch("coreason_ecosystem.fleet.pulumi_actuator.auto.select_stack"),
    ):
        mock_ws_instance = MagicMock()
        mock_stack1 = MagicMock()
        mock_stack1.name = "fleet-worker-cache"
        mock_ws_instance.list_stacks.return_value = [mock_stack1]
        mock_workspace.return_value = mock_ws_instance

        res1 = await driver_caching.reconcile_state()
        assert len(res1) == 2

        call_count1 = mock_ws_instance.list_stacks.call_count
        assert call_count1 == 2

    # Second call - cache hit (time hasn't moved 600s)
    with patch(
        "coreason_ecosystem.fleet.pulumi_actuator.auto.LocalWorkspace"
    ) as mock_workspace_2:
        mock_ws_instance_2 = MagicMock()
        mock_workspace_2.return_value = mock_ws_instance_2

        res2 = await driver_caching.reconcile_state()
        assert len(res2) == 2
        mock_ws_instance_2.list_stacks.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_state_ttl_expiration(driver_caching: PulumiActuator) -> None:
    """Boundary test: 600.0s TTL expires, forcing a hard refresh."""
    with (
        patch(
            "coreason_ecosystem.fleet.pulumi_actuator.auto.LocalWorkspace"
        ) as mock_workspace,
        patch("coreason_ecosystem.fleet.pulumi_actuator.auto.select_stack"),
    ):
        mock_ws = MagicMock()
        mock_workspace.return_value = mock_ws

        # Populate cache
        await driver_caching.reconcile_state()

        # Fast forward time
        driver_caching._last_sync_time = time.time() - 601.0

        # Should call workspace again
        await driver_caching.reconcile_state()
        assert mock_ws.list_stacks.call_count == 4


@pytest.mark.asyncio
async def test_provision_invalidates_cache(driver_caching: PulumiActuator) -> None:
    """Event-driven validation: provision_node zeroes _last_sync_time."""
    driver_caching._last_sync_time = time.time()
    driver_caching._cached_stacks = [{"stack_name": "test", "provider": "aws"}]

    target = ComputeNodeTarget(
        provider="aws",
        instance_id="t3.micro",
        hourly_cost=0.01,
        vram_gb=0.0,
        escrow_policy=EscrowPolicy(
            escrow_locked_magnitude=10000,
            release_condition_metric="t",
            refund_target_node_cid="did",
        ),
    )

    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto") as mock_auto:
        mock_stack = MagicMock()
        mock_auto.create_stack.return_value = mock_stack

        await driver_caching.provision_node(target)

        assert driver_caching._last_sync_time == 0.0


@pytest.mark.asyncio
async def test_destroy_invalidates_cache(driver_caching: PulumiActuator) -> None:
    """Event-driven validation: destroy_node zeroes _last_sync_time."""
    driver_caching._last_sync_time = time.time()
    driver_caching._cached_stacks = [{"stack_name": "test", "provider": "aws"}]

    with patch("coreason_ecosystem.fleet.pulumi_actuator.auto"):
        await driver_caching.destroy_node("fleet-worker-test", "aws")
        assert driver_caching._last_sync_time == 0.0


@pytest.mark.asyncio
async def test_thundering_herd_lock(driver_caching: PulumiActuator) -> None:
    """Edge Case: Concurrent reconcile calls serialize around the asyncio lock."""
    call_count = 0

    async def mock_to_thread(
        func: Any, *args: Any, **kwargs: Any
    ) -> list[dict[str, Any]]:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return [{"stack_name": "fleet-worker-lock", "provider": "aws"}]

    with patch("asyncio.to_thread", new=mock_to_thread):
        tasks = [
            asyncio.create_task(driver_caching.reconcile_state()),
            asyncio.create_task(driver_caching.reconcile_state()),
            asyncio.create_task(driver_caching.reconcile_state()),
        ]

        res = await asyncio.gather(*tasks)

        assert all(len(r) == 1 for r in res)
        # Due to lock & cache, inner thread block only executed once!
        assert call_count == 1
