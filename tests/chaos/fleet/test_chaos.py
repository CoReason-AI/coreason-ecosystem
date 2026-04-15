# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

from typing import Any
from unittest.mock import patch, AsyncMock

import pytest

from coreason_ecosystem.orchestration.chaos import execute_infrastructure_chaos


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile, mock_success, expected_vector, expected_node, expected_success",
    [
        # Default profile successfully executed
        ({}, True, "container_crash", "node-0", True),
        # Custom profile successfully executed
        (
            {"attack_vector": "network_partition", "target_node": "node-7"},
            True,
            "network_partition",
            "node-7",
            True,
        ),
        # Failure case with custom attack vector
        (
            {"attack_vector": "memory_pressure"},
            False,
            "memory_pressure",
            "node-0",
            False,
        ),
    ],
)
@patch("coreason_ecosystem.orchestration.chaos.random.choice")
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_chaos_execution(
    mock_sleep: AsyncMock,
    mock_choice: Any,
    profile: dict[str, Any],
    mock_success: bool,
    expected_vector: str,
    expected_node: str,
    expected_success: bool,
) -> None:
    """Test chaos execution permutations parameterized for easier AI maintainability."""
    mock_choice.return_value = mock_success

    result = await execute_infrastructure_chaos(profile)

    assert result["attack_vector"] == expected_vector
    assert result["target_node"] == expected_node
    assert result["success"] is expected_success

    if expected_success:
        assert "experiment_id" in result
        assert result["experiment_id"].startswith("chaos-")
        assert "elapsed_ms" in result
