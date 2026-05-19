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

import pytest

from coreason_ecosystem.orchestration.chaos import execute_infrastructure_chaos


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile, expected_vector, expected_node, expected_success",
    [
        # Default profile (node doesn't exist, should fail gracefully)
        ({}, "container_crash", "node-0", False),
        # Custom profile
        (
            {"attack_vector": "network_partition", "target_node": "node-7"},
            "network_partition",
            "node-7",
            True,
        ),
        # Failure case with custom attack vector
        (
            {"attack_vector": "memory_pressure"},
            "memory_pressure",
            "node-0",
            True,
        ),
    ],
)
async def test_chaos_execution(
    profile: dict[str, Any],
    expected_vector: str,
    expected_node: str,
    expected_success: bool,
) -> None:
    """Test chaos execution permutations parameterized for easier AI maintainability."""
    result = await execute_infrastructure_chaos(profile)

    assert result["attack_vector"] == expected_vector
    assert result["target_node"] == expected_node
    assert result["success"] is expected_success

    assert "experiment_id" in result
    assert result["experiment_id"].startswith("chaos-")
    assert "elapsed_ms" in result
