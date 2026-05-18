from pathlib import Path
from unittest import mock

import jwt
import pytest

from coreason_ecosystem.auth.distr_provisioning import init_vault, issue_license


from typing import Generator

@pytest.fixture
def mock_vault_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Mock the home directory so vault goes to tmp_path."""
    vault_dir = tmp_path / "vault"
    master_key = vault_dir / "master.pem"

    with (
        mock.patch("coreason_ecosystem.auth.distr_provisioning.VAULT_DIR", vault_dir),
        mock.patch(
            "coreason_ecosystem.auth.distr_provisioning.MASTER_KEY_FILE", master_key
        ),
    ):
        yield vault_dir


def test_init_vault_and_issue_license(mock_vault_dir: Path) -> None:
    # 1. Init Vault
    init_vault()
    master_key_path = mock_vault_dir / "master.pem"
    assert master_key_path.exists()

    # Init again should fail
    with pytest.raises(FileExistsError):
        init_vault()

    # 2. Issue License
    token = issue_license(
        tenant_cid="client_abc123",
        entitlements=["COMMERCIAL_USE", "PRIVATE_MESH"],
        valid_days=30,
    )

    assert isinstance(token, str)
    assert len(token) > 50

    # 3. Verify standard decoding without signature (since pubkey exported in CLI)
    decoded = jwt.decode(token, options={"verify_signature": False})

    assert decoded["tenant_cid"] == "client_abc123"
    assert "COMMERCIAL_USE" in decoded["entitlements"]
    assert decoded["network_mode"] == "private"
