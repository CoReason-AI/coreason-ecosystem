# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

from typing import Dict


class ZeroCopyStreamingMock:
    """
    AGENT INSTRUCTION: Mocks zero-copy streaming via FlatBuffers/binary streaming for tests.

    CAUSAL AFFORDANCE: Allows capability fetching in unit tests without a true network buffer.

    EPISTEMIC BOUNDS: Bounded entirely to local memory blobs mapping CID strings to bytes.

    MCP ROUTING TRIGGERS: Zero-Copy Streaming, FlatBuffers Mock, P2P Fetch
    """

    def __init__(self) -> None:
        self._blobs: Dict[str, bytes] = {}

    def store_blob(self, cid: str, data: bytes) -> None:
        self._blobs[cid] = data

    def handle_fetch_intent(self, cid_str: str) -> bytes:
        """DEPRECATED: FederatedCIDFetchIntent was removed from v0.56.0.
        Directly fetching by CID string for now.
        """
        return self._blobs.get(cid_str, b"")
