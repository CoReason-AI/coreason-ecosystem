# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock


from coreason_ecosystem.orchestration.curriculum import compile_dpo_dataset


def _make_mock_ledger_db(
    table_name: str = "gold_reward_receipts",
    has_table: bool = True,
    rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Create a mock LanceDB connection with optional DataFrame return."""
    mock_db = MagicMock()
    if has_table:
        mock_db.table_names.return_value = [table_name]
    else:
        mock_db.table_names.return_value = []

    if rows is not None:
        import pandas as pd

        df = pd.DataFrame(rows)
        mock_table = MagicMock()
        mock_table.to_pandas.return_value = df
        mock_db.open_table.return_value = mock_table

    return mock_db


def test_compile_dpo_no_table() -> None:
    """Test when the target table does not exist."""
    mock_db = _make_mock_ledger_db(has_table=False)
    result = compile_dpo_dataset(mock_db)
    assert result["total_traces"] == 0
    assert result["export_path"] is None


def test_compile_dpo_empty_table() -> None:
    """Test when the table exists but is empty."""
    mock_db = _make_mock_ledger_db(has_table=True, rows=[])
    result = compile_dpo_dataset(mock_db)
    assert result["total_traces"] == 0
    assert result["export_path"] is None


def test_compile_dpo_with_data(tmp_path: Path) -> None:
    """Test DPO compilation with actual data rows."""
    rows = [
        {
            "trace_id": f"trace-{i}",
            "total_advantage_score": float(i),
            "topology_class": "linear",
            "tokens_consumed": 100 * i,
        }
        for i in range(1, 21)
    ]
    mock_db = _make_mock_ledger_db(rows=rows)
    output_path = tmp_path / "dpo_export.jsonl"

    result = compile_dpo_dataset(
        mock_db, output_path=output_path, percentile_threshold=10.0
    )

    assert result["total_traces"] == 20
    assert result["chosen_count"] > 0
    assert result["rejected_count"] > 0
    assert result["dpo_pair_count"] > 0
    assert result["export_path"] == str(output_path)

    # Verify JSONL output
    assert output_path.exists()
    with output_path.open() as f:
        lines = f.readlines()
    assert len(lines) == result["dpo_pair_count"]

    # Verify structure of each line
    for line in lines:
        pair = json.loads(line)
        assert "prompt" in pair
        assert "chosen" in pair
        assert "rejected" in pair
        assert "trace_id" in pair["chosen"]
        assert "advantage_score" in pair["chosen"]


def test_compile_dpo_default_output_path() -> None:
    """Test that default output path is used when none specified."""
    rows = [
        {
            "trace_id": f"t-{i}",
            "total_advantage_score": float(i),
            "topology_class": "dag",
            "tokens_consumed": 50,
        }
        for i in range(1, 11)
    ]
    mock_db = _make_mock_ledger_db(rows=rows)

    result = compile_dpo_dataset(mock_db)

    expected_path = "./curriculum_dpo_export.jsonl"
    assert result["export_path"] == expected_path

    # Clean up
    output = Path(expected_path)
    if output.exists():
        output.unlink()
