# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""
Federation module for inter-instance CoReason communication.

This module provides the core identity and proxy mechanisms for federated 
swarm execution across zero-trust network boundaries.
"""

# Re-export the NATS-native proxy as the primary federation mechanism
from coreason_ecosystem.wasmcloud.nats_federation import (
    NATSFederationProxy,
    FederatedExecutionReceipt,
)

# Canonical public mesh identity constants
COREASON_PUBLIC_INSTANCE_ID = "mesh.coreason.ai"
COREASON_PUBLIC_TENANT_CID = (
    "889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531"
)
COREASON_PUBLIC_SPIFFE_DOMAIN = "spiffe://mesh.coreason.ai"

__all__ = [
    "COREASON_PUBLIC_INSTANCE_ID",
    "COREASON_PUBLIC_SPIFFE_DOMAIN",
    "COREASON_PUBLIC_TENANT_CID",
    "FederatedExecutionReceipt",
    "NATSFederationProxy",
]
