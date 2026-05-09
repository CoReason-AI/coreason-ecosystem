# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

from typing import Dict, List, Set


class KademliaDHTMock:
    """
    AGENT INSTRUCTION: Mock implementation of Kademlia DHT logic for mapping CIDs to peer IPs.

    CAUSAL AFFORDANCE: Simulates the Distributed Hash Table for zero-trust P2P local routing.

    EPISTEMIC BOUNDS: Operates in memory. Replaces true DHT for testing environments.

    MCP ROUTING TRIGGERS: Kademlia, DHT, P2P, Mock Routing
    """

    def __init__(self) -> None:
        self._store: Dict[str, Set[str]] = {}

    def store_capability(self, cid: str, peer_ip: str) -> None:
        if cid not in self._store:
            self._store[cid] = set()
        self._store[cid].add(peer_ip)

    def resolve_capability(self, cid: str) -> List[str]:
        return list(self._store.get(cid, set()))
