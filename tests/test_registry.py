# Copyright (c) 2026 CoReason, Inc.
# Licensed under the Prosperity Public License 3.0

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch
import json

from coreason_ecosystem.orchestration.registry import calculate_epistemic_root, read_registry_lock, write_registry_lock


@patch("coreason_ecosystem.orchestration.registry.Path.exists")
@patch("coreason_ecosystem.orchestration.registry.Path.read_bytes")
@patch("coreason_ecosystem.orchestration.registry.subprocess.run")
def test_calculate_epistemic_root(mock_sub_run: Any, mock_read_bytes: Any, mock_exists: Any) -> None:
    mock_exists.return_value = True
    mock_read_bytes.side_effect = [b'{"title": "ontology"}', b'{"cap": "hash"}']
    mock_sub_run.return_value.stdout = "version 1.0"

    root = asyncio.run(calculate_epistemic_root(Path("/tmp")))
    assert root is not None
    assert isinstance(root, str)
    assert len(root) == 64

@patch("coreason_ecosystem.orchestration.registry.Path.exists")
@patch("coreason_ecosystem.orchestration.registry.subprocess.run")
def test_calculate_epistemic_root_missing_files(mock_sub_run: Any, mock_exists: Any) -> None:
    mock_exists.return_value = False
    mock_sub_run.return_value.stdout = "version 1.0"

    root = asyncio.run(calculate_epistemic_root(Path("/tmp")))
    assert root is not None
    assert isinstance(root, str)
    assert len(root) == 64

@patch("coreason_ecosystem.orchestration.registry.Path.write_text")
@patch("coreason_ecosystem.orchestration.registry.Path.mkdir")
def test_write_registry_lock(mock_mkdir: Any, mock_write_text: Any) -> None:
    write_registry_lock(Path("/tmp"), "deadbeef")
    mock_mkdir.assert_called_once()
    mock_write_text.assert_called_once_with("deadbeef", encoding="utf-8")


@patch("coreason_ecosystem.orchestration.registry.Path.exists")
@patch("coreason_ecosystem.orchestration.registry.Path.read_text")
def test_read_registry_lock(mock_read_text: Any, mock_exists: Any) -> None:
    mock_exists.return_value = True
    mock_read_text.return_value = "deadbeef"
    assert read_registry_lock(Path("/tmp")) == "deadbeef"

@patch("coreason_ecosystem.orchestration.registry.Path.exists")
def test_read_registry_lock_missing(mock_exists: Any) -> None:
    mock_exists.return_value = False
    assert read_registry_lock(Path("/tmp")) is None
