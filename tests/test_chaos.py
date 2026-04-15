# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from unittest.mock import patch, AsyncMock

import pytest

from coreason_ecosystem.orchestration.chaos import execute_infrastructure_chaos


@pytest.mark.asyncio
async def test_chaos_default_profile() -> None:
    """Test chaos execution with default attack_vector and target_node."""
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch("random.choice", return_value=True):
            result = await execute_infrastructure_chaos({})

    assert result["attack_vector"] == "container_crash"
    assert result["target_node"] == "node-0"
    assert result["success"] is True
    assert "experiment_id" in result
    assert result["experiment_id"].startswith("chaos-")
    assert "elapsed_ms" in result


@pytest.mark.asyncio
async def test_chaos_custom_profile_success() -> None:
    """Test chaos with custom profile and success."""
    profile = {
        "attack_vector": "network_partition",
        "target_node": "node-7",
    }
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch("random.choice", return_value=True):
            result = await execute_infrastructure_chaos(profile)

    assert result["attack_vector"] == "network_partition"
    assert result["target_node"] == "node-7"
    assert result["success"] is True


@pytest.mark.asyncio
async def test_chaos_failure() -> None:
    """Test chaos execution when the fleet fails."""
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch("random.choice", return_value=False):
            result = await execute_infrastructure_chaos(
                {"attack_vector": "memory_pressure"}
            )

    assert result["success"] is False
    assert result["attack_vector"] == "memory_pressure"
