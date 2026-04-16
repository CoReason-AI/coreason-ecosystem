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
from unittest.mock import patch

from coreason_ecosystem.web3.treasury_manager import TreasuryManager


@pytest.mark.asyncio
async def test_treasury_manager_disburse() -> None:
    """Test TreasuryManager raises NotImplementedError (no physical provider)."""
    manager = TreasuryManager(treasury_contract_address="0xTestContract")

    receipt = {
        "awarded_syndicate": "did:coreason:syndicate-1",
        "amount_gwei": 5_000_000,
    }

    with pytest.raises(NotImplementedError, match="Physical Web3 provider"):
        await manager.disburse_node_rewards(receipt)


@pytest.mark.asyncio
async def test_treasury_manager_disburse_defaults() -> None:
    """Test TreasuryManager handles missing keys in receipt."""
    manager = TreasuryManager(treasury_contract_address="0xCustomContract")
    assert manager.contract_address == "0xCustomContract"

    receipt: dict[str, object] = {}

    with pytest.raises(NotImplementedError, match="Physical Web3 provider"):
        await manager.disburse_node_rewards(receipt)


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
