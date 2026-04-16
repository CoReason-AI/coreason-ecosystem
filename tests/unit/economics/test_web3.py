# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import pytest
from unittest.mock import AsyncMock, patch

from coreason_ecosystem.web3.treasury_manager import (
    MockWeb3Provider,
    TreasuryManager,
)


@pytest.mark.asyncio
async def test_mock_web3_provider_broadcast() -> None:
    """Test MockWeb3Provider broadcasts a transaction and returns a hash."""
    with patch("asyncio.sleep", new_callable=AsyncMock):
        tx_hash = await MockWeb3Provider.broadcast_tx(
            "0xContract", {"function": "test"}
        )
    assert tx_hash.startswith("0x")
    assert len(tx_hash) == 18  # 0x + 16 hex chars


@pytest.mark.asyncio
async def test_treasury_manager_disburse() -> None:
    """Test TreasuryManager disburses rewards correctly."""
    manager = TreasuryManager(treasury_contract_address="0xTestContract")

    receipt = {
        "awarded_syndicate": "did:coreason:syndicate-1",
        "amount_gwei": 5_000_000,
    }

    with patch("asyncio.sleep", new_callable=AsyncMock):
        tx_hash = await manager.disburse_node_rewards(receipt)

    assert tx_hash.startswith("0x")


@pytest.mark.asyncio
async def test_treasury_manager_disburse_defaults() -> None:
    """Test TreasuryManager handles missing keys in receipt."""
    manager = TreasuryManager(treasury_contract_address="0xCustomContract")
    assert manager.contract_address == "0xCustomContract"

    receipt: dict[str, object] = {}

    with patch("asyncio.sleep", new_callable=AsyncMock):
        tx_hash = await manager.disburse_node_rewards(receipt)

    assert tx_hash.startswith("0x")


def test_treasury_manager_env_injection() -> None:
    """Test that TreasuryManager resolves contract address from env."""
    with patch.dict("os.environ", {"COREASON_TREASURY_CONTRACT": "0xEnvContract"}):
        manager = TreasuryManager()
        assert manager.contract_address == "0xEnvContract"


def test_treasury_manager_no_address_warns() -> None:
    """Test that TreasuryManager warns when no contract address is configured."""
    with patch.dict("os.environ", {}, clear=True):
        manager = TreasuryManager()
        assert manager.contract_address == ""
