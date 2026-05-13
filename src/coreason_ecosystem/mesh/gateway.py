# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

from typing import List

from coreason_manifest.spec.ontology import FederatedDiscoveryIntent

from .dht import KademliaDHTMock


class MeshGateway:
    """
    AGENT INSTRUCTION: Mesh gateway node for P2P discovery within a strict zero-trust boundary.

    CAUSAL AFFORDANCE: Resolves FederatedDiscoveryIntent structurally against the local DHT mock.

    EPISTEMIC BOUNDS: No outbound HTTP calls. Fully mocked resolution surface.

    MCP ROUTING TRIGGERS: Mesh Gateway, P2P Discovery, Routing Fabric
    """

    def __init__(self, dht: KademliaDHTMock) -> None:
        self.dht = dht

    def handle_discovery_intent(self, intent: FederatedDiscoveryIntent) -> List[str]:
        """Handles a discovery intent and returns a list of peer IPs."""
        results: List[str] = []
        for urn, ips in self.dht._store.items():
            # Check domain filter
            if not intent.domain_filter:
                results.extend(list(ips))
                continue

            for domain in intent.domain_filter:
                # Match domain in URN (e.g. urn:coreason:actionspace:solver:...)
                if f":{domain}:" in urn or urn.endswith(f":{domain}"):
                    results.extend(list(ips))
                    break
        return sorted(list(set(results)))
