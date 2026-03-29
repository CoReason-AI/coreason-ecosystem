# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch
import importlib.metadata

from coreason_ecosystem.orchestration.registry import (
    calculate_epistemic_root,
    read_registry_lock,
    write_registry_lock,
)


@patch("importlib.metadata.version")
@patch("coreason_ecosystem.orchestration.registry.Path.exists")
@patch("coreason_ecosystem.orchestration.registry.Path.read_bytes")
def test_calculate_epistemic_root(
    mock_read_bytes: Any, mock_exists: Any, mock_version: Any
) -> None:
    mock_exists.return_value = True
    mock_read_bytes.side_effect = [b'{"title": "ontology"}', b'{"cap": "hash"}']
    mock_version.return_value = "1.0"

    root = asyncio.run(calculate_epistemic_root(Path("/tmp")))
    assert root is not None
    assert isinstance(root, str)
    assert len(root) == 64


@patch("importlib.metadata.version")
@patch("coreason_ecosystem.orchestration.registry.Path.exists")
def test_calculate_epistemic_root_missing_files(
    mock_exists: Any, mock_version: Any
) -> None:
    mock_exists.return_value = False
    mock_version.side_effect = importlib.metadata.PackageNotFoundError()

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
