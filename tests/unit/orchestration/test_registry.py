import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from coreason_ecosystem.orchestration.registry import (
    calculate_epistemic_root,
    write_registry_lock,
    read_registry_lock,
)


@pytest.mark.asyncio
async def test_calculate_epistemic_root_all_files_exist(tmp_path: Path) -> None:
    schema_path = tmp_path / "coreason_ontology.schema.json"
    schema_path.write_bytes(b"test schema")

    ledger_path = tmp_path / ".coreason" / "capability_ledger.json"
    ledger_path.parent.mkdir()
    ledger_path.write_bytes(b'{"test": "ledger"}')

    with patch("importlib.metadata.version") as mock_version:
        mock_version.return_value = "1.0.0"
        root = await calculate_epistemic_root(tmp_path)

        # Verify hashes manually
        h_ontology = hashlib.sha256(b"test schema").hexdigest()
        env_str = "coreason-manifest==1.0.0\ncoreason-runtime==1.0.0\n"
        h_env = hashlib.sha256(env_str.encode("utf-8")).hexdigest()
        h_cap = hashlib.sha256(b'{"test": "ledger"}').hexdigest()
        expected = hashlib.sha256(
            (h_ontology + h_env + h_cap).encode("utf-8")
        ).hexdigest()

        assert root == expected


@pytest.mark.asyncio
async def test_calculate_epistemic_root_missing_files_package_error(
    tmp_path: Path,
) -> None:
    from importlib.metadata import PackageNotFoundError

    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        root = await calculate_epistemic_root(tmp_path)

        h_ontology = hashlib.sha256(b"").hexdigest()
        env_str = "coreason-manifest==unknown\ncoreason-runtime==unknown\n"
        h_env = hashlib.sha256(env_str.encode("utf-8")).hexdigest()
        h_cap = hashlib.sha256(b"{}").hexdigest()
        expected = hashlib.sha256(
            (h_ontology + h_env + h_cap).encode("utf-8")
        ).hexdigest()

        assert root == expected


def test_write_registry_lock(tmp_path: Path) -> None:
    write_registry_lock(tmp_path, "test_root_hash")
    lock_file = tmp_path / ".coreason" / "registry.lock"
    assert lock_file.exists()
    data = json.loads(lock_file.read_text())
    assert data["epistemic_root"] == "test_root_hash"


def test_read_registry_lock_valid(tmp_path: Path) -> None:
    lock_file = tmp_path / ".coreason" / "registry.lock"
    lock_file.parent.mkdir()
    lock_file.write_text('{"epistemic_root": "test_hash"}')

    assert read_registry_lock(tmp_path) == "test_hash"


def test_read_registry_lock_invalid_json(tmp_path: Path) -> None:
    lock_file = tmp_path / ".coreason" / "registry.lock"
    lock_file.parent.mkdir()
    lock_file.write_text("invalid_hash_string")

    assert read_registry_lock(tmp_path) == "invalid_hash_string"


def test_read_registry_lock_missing(tmp_path: Path) -> None:
    assert read_registry_lock(tmp_path) is None
