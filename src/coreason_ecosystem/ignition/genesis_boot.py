# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Genesis Boot: Mainnet Ignition & Foundational State Minting.

Executes the one-time cryptographic bootstrapping of the CoReason Mainnet.
Mints the foundational WorkflowManifest on a pristine LanceDB ledger,
anchors the ConstitutionalPolicy, generates root cryptographic keys,
and exports the network_bootstrap.json for edge node onboarding.

CRITICAL: This script is designed to run EXACTLY ONCE per swarm.
It mathematically locks itself out if an EpistemicLedgerState already exists.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger


# ── Constitutional Constants ───────────────────────────────────────────

GENESIS_PROTOCOL_VERSION = "1.0.0"

CONSTITUTIONAL_POLICY: dict[str, Any] = {
    "protocol_name": "CoReason Constitutional Policy",
    "version": GENESIS_PROTOCOL_VERSION,
    "license": "Prosperity Public License 3.0",
    "license_uri": "https://prosperitylicense.com/versions/3.0.0",
    "immutable_constraints": [
        "No instrumental convergence beyond declared task boundaries.",
        "All reasoning traces must be auditable via the Epistemic Ledger.",
        "Human-in-the-Loop Oracle authority cannot be overridden by autonomous agents.",
        "Physical actuation requires WetwareAttestationContract (biometric sign-off).",
        "Cross-tenant data sharing requires bilateral SLA alignment.",
    ],
    "governance_model": "Decentralized Constitutional Adjudication",
    "max_autonomy_level": "supervised",
}


async def mint_genesis_block(
    tenant_name: str,
    config_path: str | None = None,
    lancedb_uri: str = "./genesis_ledger",
) -> dict[str, Any]:
    """Mint the foundational genesis block for the CoReason Mainnet.

    This function runs EXACTLY ONCE per swarm. It mathematically locks
    itself out if an EpistemicLedgerState already exists.

    Args:
        tenant_name: The founding tenant/organization name.
        config_path: Optional path to a config JSON file.
        lancedb_uri: URI for the LanceDB instance.

    Returns:
        A GenesisReceipt dict with the minted state and bootstrap config.

    Raises:
        RuntimeError: If a ledger already exists (genesis already happened).
    """
    import pyarrow as pa  # type: ignore

    receipt: dict[str, Any] = {
        "genesis_id": f"genesis-{uuid.uuid4()}",
        "tenant_name": tenant_name,
        "protocol_version": GENESIS_PROTOCOL_VERSION,
        "started_at_ns": time.time_ns(),
    }

    # ── Guard: Exactly-Once Execution ──────────────────────────────
    try:
        import lancedb  # type: ignore

        db = lancedb.connect(lancedb_uri)
    except Exception as e:
        logger.error(f"[Genesis] Failed to connect to LanceDB at {lancedb_uri}: {e}")
        raise RuntimeError(f"LanceDB connection failed: {e}") from e

    if "gold_ledger" in db.table_names():
        msg = (
            "GENESIS ABORT: EpistemicLedgerState already exists. "
            "The genesis block has already been minted for this swarm. "
            "This script can only run EXACTLY ONCE per swarm."
        )
        logger.error(f"[Genesis] {msg}")
        raise RuntimeError(msg)

    logger.info(f"[Genesis] Minting genesis block for tenant '{tenant_name}'...")

    # ── Step 1: Generate Root Cryptographic Identity ───────────────
    root_cid = f"root-{uuid.uuid4()}"
    root_key_seed = hashlib.sha256(
        f"{root_cid}:{tenant_name}:{time.time_ns()}".encode()
    ).hexdigest()

    receipt["root_cid"] = root_cid
    receipt["root_key_fingerprint"] = root_key_seed[:16]

    # ── Step 2: Mint the Root WorkflowManifest ─────────────────────
    genesis_manifest: dict[str, Any] = {
        "manifest_cid": f"manifest-{uuid.uuid4()}",
        "tenant_cid": root_cid,
        "session_cid": f"genesis-session-{uuid.uuid4()}",
        "protocol_version": GENESIS_PROTOCOL_VERSION,
        "constitutional_policy": CONSTITUTIONAL_POLICY,
        "governance": {
            "max_global_tokens": 10_000_000,
            "max_budget_magnitude": 1000.0,
            "global_timeout_seconds": 3600,
        },
        "created_at_ns": time.time_ns(),
        "genesis_block": True,
    }

    receipt["genesis_manifest_cid"] = genesis_manifest["manifest_cid"]

    # ── Step 3: Write Gold Ledger (Medallion State Engine) ─────────
    _gold_schema = pa.schema([
        pa.field("intent_hash", pa.string()),
        pa.field("tenant_cid", pa.string()),
        pa.field("session_cid", pa.string()),
        pa.field("payload", pa.string()),
        pa.field("timestamp_ns", pa.int64()),
        pa.field("is_genesis", pa.bool_()),
    ])

    genesis_record = pa.table({
        "intent_hash": [hashlib.sha256(
            json.dumps(genesis_manifest, sort_keys=True).encode()
        ).hexdigest()],
        "tenant_cid": [root_cid],
        "session_cid": [genesis_manifest["session_cid"]],
        "payload": [json.dumps(genesis_manifest, sort_keys=True)],
        "timestamp_ns": [time.time_ns()],
        "is_genesis": [True],
    })

    db.create_table("gold_ledger", genesis_record)
    logger.info("[Genesis] Gold Medallion ledger initialized with genesis block.")

    # ── Step 4: Create Silver & Bronze tables ──────────────────────
    _silver_schema = pa.schema([
        pa.field("event_cid", pa.string()),
        pa.field("event_type", pa.string()),
        pa.field("payload", pa.string()),
        pa.field("timestamp_ns", pa.int64()),
    ])
    db.create_table("silver_standardized", pa.table({
        "event_cid": [f"silver-genesis-{uuid.uuid4()}"],
        "event_type": ["GENESIS_INIT"],
        "payload": [json.dumps({"genesis": True})],
        "timestamp_ns": [time.time_ns()],
    }))

    _bronze_schema = pa.schema([
        pa.field("raw_cid", pa.string()),
        pa.field("entropy_source", pa.string()),
        pa.field("timestamp_ns", pa.int64()),
    ])
    db.create_table("bronze_entropy", pa.table({
        "raw_cid": [f"bronze-genesis-{uuid.uuid4()}"],
        "entropy_source": ["genesis_boot"],
        "timestamp_ns": [time.time_ns()],
    }))

    logger.info("[Genesis] Silver & Bronze Medallion tables initialized.")

    # ── Step 5: Export network_bootstrap.json ───────────────────────
    bootstrap_config: dict[str, Any] = {
        "swarm_id": root_cid,
        "tenant_name": tenant_name,
        "protocol_version": GENESIS_PROTOCOL_VERSION,
        "genesis_manifest_cid": genesis_manifest["manifest_cid"],
        "root_key_fingerprint": root_key_seed[:16],
        "lancedb_uri": lancedb_uri,
        "constitutional_policy_hash": hashlib.sha256(
            json.dumps(CONSTITUTIONAL_POLICY, sort_keys=True).encode()
        ).hexdigest(),
        "federation": {
            "beacon_endpoint": "/api/v1/federation/beacon",
            "onboard_endpoint": "/api/v1/federation/onboard",
            "gossip_interval_seconds": 60,
        },
        "created_at_ns": time.time_ns(),
    }

    bootstrap_path = Path(config_path or "./network_bootstrap.json")
    bootstrap_path.write_text(
        json.dumps(bootstrap_config, indent=2), encoding="utf-8"
    )

    receipt["bootstrap_config_path"] = str(bootstrap_path)
    receipt["bootstrap_config"] = bootstrap_config
    receipt["completed_at_ns"] = time.time_ns()
    receipt["status"] = "GENESIS_COMPLETE"

    elapsed_ms = (receipt["completed_at_ns"] - receipt["started_at_ns"]) / 1_000_000
    receipt["elapsed_ms"] = round(elapsed_ms, 2)

    logger.info(
        f"[Genesis] MAINNET IGNITED for '{tenant_name}' in {elapsed_ms:.1f}ms. "
        f"Root CID: {root_cid[:24]}..."
    )

    return receipt
