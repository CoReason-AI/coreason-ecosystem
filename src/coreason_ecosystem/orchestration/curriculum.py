# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Curriculum Distillation for Direct Preference Optimization (DPO).

Aggregates high-reward cognitive reasoning traces from the LanceDB
Gold Medallion ledger and exports them as strict (prompt, chosen, rejected)
tuple pairs in JSONL format for offline LLM fine-tuning pipelines.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger


def compile_dpo_dataset(
    ledger_db: Any,
    output_path: Path | None = None,
    percentile_threshold: float = 10.0,
) -> dict[str, Any]:
    """Compile a DPO-ready JSONL dataset from the reward ledger.

    Queries the Gold Medallion ledger for CognitiveRewardEvaluationReceipts.
    Traces in the top percentile_threshold% are labeled 'chosen',
    traces in the bottom percentile_threshold% are labeled 'rejected'.

    Args:
        ledger_db: A LanceDB connection instance.
        output_path: Optional path to write the .jsonl file. Defaults to
            './curriculum_dpo_export.jsonl'.
        percentile_threshold: The percentile cutoff (default 10.0 = top/bottom 10%).

    Returns:
        An EpistemicCurriculumManifest dict with metadata and export path.
    """
    table_name = "gold_reward_receipts"

    if table_name not in ledger_db.table_names():
        logger.warning(f"Table '{table_name}' not found. No receipts to export.")
        return {
            "total_traces": 0,
            "chosen_count": 0,
            "rejected_count": 0,
            "export_path": None,
        }

    table = ledger_db.open_table(table_name)
    df = table.to_pandas()

    if df.empty:
        logger.warning("Reward receipt table is empty.")
        return {
            "total_traces": 0,
            "chosen_count": 0,
            "rejected_count": 0,
            "export_path": None,
        }

    # Calculate percentile boundaries
    upper_bound = df["total_advantage_score"].quantile(
        1.0 - percentile_threshold / 100.0
    )
    lower_bound = df["total_advantage_score"].quantile(percentile_threshold / 100.0)

    chosen_traces = df[df["total_advantage_score"] >= upper_bound]
    rejected_traces = df[df["total_advantage_score"] <= lower_bound]

    logger.info(
        f"Curriculum: {len(chosen_traces)} chosen (>= {upper_bound:.4f}), "
        f"{len(rejected_traces)} rejected (<= {lower_bound:.4f}) "
        f"from {len(df)} total traces."
    )

    # Build DPO pairs: pair each chosen with each rejected
    dpo_pairs: list[dict[str, Any]] = []
    for _, chosen_row in chosen_traces.iterrows():
        for _, rejected_row in rejected_traces.iterrows():
            pair = {
                "prompt": f"Reasoning task [trace:{chosen_row['trace_id']}]",
                "chosen": {
                    "trace_id": str(chosen_row["trace_id"]),
                    "advantage_score": float(chosen_row["total_advantage_score"]),
                    "topology_class": str(chosen_row["topology_class"]),
                    "tokens_consumed": int(chosen_row["tokens_consumed"]),
                },
                "rejected": {
                    "trace_id": str(rejected_row["trace_id"]),
                    "advantage_score": float(rejected_row["total_advantage_score"]),
                    "topology_class": str(rejected_row["topology_class"]),
                    "tokens_consumed": int(rejected_row["tokens_consumed"]),
                },
            }
            dpo_pairs.append(pair)

    # Export to JSONL
    if output_path is None:
        output_path = Path("./curriculum_dpo_export.jsonl")

    with open(output_path, "w") as f:
        for pair in dpo_pairs:
            f.write(json.dumps(pair) + "\n")

    logger.info(f"Exported {len(dpo_pairs)} DPO pairs to {output_path}")

    manifest: dict[str, Any] = {
        "total_traces": len(df),
        "chosen_count": len(chosen_traces),
        "rejected_count": len(rejected_traces),
        "dpo_pair_count": len(dpo_pairs),
        "upper_percentile_bound": round(float(upper_bound), 6),
        "lower_percentile_bound": round(float(lower_bound), 6),
        "export_path": str(output_path),
        "percentile_threshold": percentile_threshold,
    }

    return manifest
