# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

"""Tests for the federation module — air gap policies, proxy, and audit."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from coreason_ecosystem.federation.policy import (
    AirGapPolicy,
    ConnectivityDirection,
    ContributionIntent,
    ContributionPolicy,
    FederationAgreementState,
    FederationPeerState,
    InstanceType,
)
from coreason_ecosystem.federation.proxy import (
    FederatedExecutionReceipt,
    FederationProxy,
)


# ---------------------------------------------------------------------------
# Fixtures: reusable peer and agreement states
# ---------------------------------------------------------------------------

PRIVATE_PEER = FederationPeerState(
    instance_id="alpha.enterprise.internal",
    instance_type=InstanceType.PRIVATE,
    spiffe_trust_domain="spiffe://alpha.enterprise.internal",
    gateway_endpoint="https://gateway.alpha.internal:8443",
    tenant_cid="aaaa1111",
)

PUBLIC_PEER = FederationPeerState(
    instance_id="mesh.coreason.ai",
    instance_type=InstanceType.PUBLIC,
    spiffe_trust_domain="spiffe://mesh.coreason.ai",
    trust_bundle_endpoint="https://spire.mesh.coreason.ai/.well-known/spiffe-bundle",
    gateway_endpoint="https://gateway.mesh.coreason.ai",
    tenant_cid="889955217295c2bfef2d6812071b633b0819477e67f57853febf116f69f30531",
)

PRIVATE_PEER_B = FederationPeerState(
    instance_id="beta.pharma.internal",
    instance_type=InstanceType.PRIVATE,
    spiffe_trust_domain="spiffe://beta.pharma.internal",
    gateway_endpoint="https://gateway.beta.internal:8443",
    tenant_cid="bbbb2222",
)


def _make_private_to_public_agreement(
    direction: ConnectivityDirection = ConnectivityDirection.OUTBOUND_ONLY,
    allowed_urns: list[str] | None = None,
    signed: bool = True,
) -> FederationAgreementState:
    """Create a Private→Public federation agreement."""
    return FederationAgreementState(
        agreement_id="agreement-priv-pub-001",
        initiator=PRIVATE_PEER,
        responder=PUBLIC_PEER,
        initiator_policy=AirGapPolicy(
            peer_instance_id=PUBLIC_PEER.instance_id,
            direction=direction,
            allowed_urns=allowed_urns or [],
            max_clearance="PUBLIC",
        ),
        responder_policy=None,
        signed_by_initiator=signed,
        signed_by_responder=False,
    )


def _make_private_to_private_agreement(
    signed_both: bool = True,
) -> FederationAgreementState:
    """Create a Private↔Private (DMZ) federation agreement."""
    return FederationAgreementState(
        agreement_id="agreement-dmz-001",
        initiator=PRIVATE_PEER,
        responder=PRIVATE_PEER_B,
        initiator_policy=AirGapPolicy(
            peer_instance_id=PRIVATE_PEER_B.instance_id,
            direction=ConnectivityDirection.BIDIRECTIONAL,
            max_clearance="CONFIDENTIAL",
        ),
        responder_policy=AirGapPolicy(
            peer_instance_id=PRIVATE_PEER.instance_id,
            direction=ConnectivityDirection.BIDIRECTIONAL,
            max_clearance="CONFIDENTIAL",
        ),
        signed_by_initiator=signed_both,
        signed_by_responder=signed_both,
    )


# ---------------------------------------------------------------------------
# Policy model tests
# ---------------------------------------------------------------------------


class TestAirGapPolicy:
    """Tests for AirGapPolicy model validation."""

    def test_default_policy_is_closed(self) -> None:
        policy = AirGapPolicy(peer_instance_id="test")
        assert policy.direction == ConnectivityDirection.CLOSED
        assert policy.require_dlp_scanning is True
        assert policy.require_audit_receipts is True
        assert policy.max_clearance == "PUBLIC"

    def test_allowed_urns_are_sorted(self) -> None:
        policy = AirGapPolicy(
            peer_instance_id="test",
            allowed_urns=["urn:coreason:z:tool", "urn:coreason:a:tool"],
        )
        assert policy.allowed_urns == [
            "urn:coreason:a:tool",
            "urn:coreason:z:tool",
        ]


class TestFederationPeerState:
    """Tests for FederationPeerState model."""

    def test_public_peer_has_default_clearance(self) -> None:
        assert PUBLIC_PEER.clearance == "PUBLIC"

    def test_private_peer_identity(self) -> None:
        assert PRIVATE_PEER.instance_type == InstanceType.PRIVATE
        assert PRIVATE_PEER.spiffe_trust_domain.startswith("spiffe://")


class TestFederationAgreementState:
    """Tests for FederationAgreementState lifecycle."""

    def test_private_to_public_outbound_is_active_without_responder_sig(self) -> None:
        agreement = _make_private_to_public_agreement(signed=True)
        # Private→Public outbound doesn't need responder signature
        assert agreement.is_active is True

    def test_private_to_public_unsigned_is_inactive(self) -> None:
        agreement = _make_private_to_public_agreement(signed=False)
        assert agreement.is_active is False

    def test_private_to_private_requires_both_signatures(self) -> None:
        agreement = _make_private_to_private_agreement(signed_both=True)
        assert agreement.is_active is True

    def test_private_to_private_single_sig_is_inactive(self) -> None:
        agreement = _make_private_to_private_agreement(signed_both=False)
        assert agreement.is_active is False

    def test_expired_agreement_is_inactive(self) -> None:
        agreement = _make_private_to_private_agreement(signed_both=True)
        agreement.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert agreement.is_active is False

    def test_agreement_hash_is_deterministic(self) -> None:
        agreement = _make_private_to_public_agreement()
        h1 = agreement.compute_agreement_hash()
        h2 = agreement.compute_agreement_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_agreements_produce_different_hashes(self) -> None:
        a1 = _make_private_to_public_agreement()
        a2 = _make_private_to_private_agreement()
        assert a1.compute_agreement_hash() != a2.compute_agreement_hash()


# ---------------------------------------------------------------------------
# Proxy air gap enforcement tests
# ---------------------------------------------------------------------------


class TestFederationProxyAirGap:
    """Tests for FederationProxy air gap enforcement logic."""

    def test_no_agreement_denies_access(self) -> None:
        proxy = FederationProxy(local_instance=PRIVATE_PEER)
        permitted, reason = proxy.check_air_gap(
            "unknown.instance", "urn:coreason:test", "PUBLIC"
        )
        assert permitted is False
        assert "No federation agreement" in reason

    def test_closed_policy_denies_access(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.CLOSED,
        )
        # Force it active so we test the policy check, not the agreement check
        agreement.signed_by_initiator = True
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])
        permitted, reason = proxy.check_air_gap(
            PUBLIC_PEER.instance_id, "urn:coreason:test", "PUBLIC"
        )
        assert permitted is False
        assert "CLOSED" in reason

    def test_outbound_policy_permits_access(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.OUTBOUND_ONLY
        )
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])
        permitted, reason = proxy.check_air_gap(
            PUBLIC_PEER.instance_id, "urn:coreason:test", "PUBLIC"
        )
        assert permitted is True

    def test_urn_allowlist_enforcement(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.OUTBOUND_ONLY,
            allowed_urns=["urn:coreason:actionspace:solver:*"],
        )
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        # Permitted: matches glob
        ok, _ = proxy.check_air_gap(
            PUBLIC_PEER.instance_id,
            "urn:coreason:actionspace:solver:clinical_extractor:v1",
            "PUBLIC",
        )
        assert ok is True

        # Denied: doesn't match
        ok, reason = proxy.check_air_gap(
            PUBLIC_PEER.instance_id,
            "urn:coreason:actionspace:effector:dangerous:v1",
            "PUBLIC",
        )
        assert ok is False
        assert "not in the allowlist" in reason

    def test_clearance_enforcement(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.OUTBOUND_ONLY
        )
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        # PUBLIC is fine
        ok, _ = proxy.check_air_gap(
            PUBLIC_PEER.instance_id, "urn:coreason:test", "PUBLIC"
        )
        assert ok is True

        # CONFIDENTIAL exceeds max_clearance=PUBLIC
        ok, reason = proxy.check_air_gap(
            PUBLIC_PEER.instance_id, "urn:coreason:test", "CONFIDENTIAL"
        )
        assert ok is False
        assert "exceeds max" in reason

    def test_private_to_private_bidirectional(self) -> None:
        agreement = _make_private_to_private_agreement(signed_both=True)
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        ok, _ = proxy.check_air_gap(
            PRIVATE_PEER_B.instance_id, "urn:coreason:test", "CONFIDENTIAL"
        )
        assert ok is True

    def test_list_active_peers(self) -> None:
        agreement = _make_private_to_public_agreement()
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])
        peers = proxy.list_active_peers()
        assert PUBLIC_PEER.instance_id in peers


# ---------------------------------------------------------------------------
# Proxy remote invocation tests (using respx for real HTTP interception)
# ---------------------------------------------------------------------------


class TestFederationProxyInvocation:
    """Tests for FederationProxy remote tool invocation via httpx + respx."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_remote_tool_success(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.OUTBOUND_ONLY
        )
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        # Mock the remote endpoint
        respx.post(f"{PUBLIC_PEER.gateway_endpoint}/mcp/v1/messages").respond(
            json={"jsonrpc": "2.0", "result": {"content": "hello"}, "id": "test"},
        )

        result = await proxy.invoke_remote_tool(
            PUBLIC_PEER.instance_id,
            "urn:coreason:actionspace:solver:test:v1",
            {"input": "test"},
        )

        assert result["result"]["content"] == "hello"

        # Verify audit receipt was emitted
        receipts = proxy.get_receipts()
        assert len(receipts) == 1
        assert receipts[0]["success"] is True
        assert receipts[0]["source_instance"] == PRIVATE_PEER.instance_id
        assert receipts[0]["destination_instance"] == PUBLIC_PEER.instance_id

        await proxy.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_remote_tool_denied_by_policy(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.CLOSED
        )
        # Force signed so we test the policy path, not the agreement path
        agreement.signed_by_initiator = True
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        with pytest.raises(PermissionError, match="CLOSED"):
            await proxy.invoke_remote_tool(
                PUBLIC_PEER.instance_id,
                "urn:coreason:test",
                {"input": "test"},
            )

        await proxy.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_remote_tool_http_error_emits_receipt(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.OUTBOUND_ONLY
        )
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        respx.post(f"{PUBLIC_PEER.gateway_endpoint}/mcp/v1/messages").respond(
            status_code=503, text="Service unavailable"
        )

        with pytest.raises(ConnectionError, match="503"):
            await proxy.invoke_remote_tool(
                PUBLIC_PEER.instance_id,
                "urn:coreason:test",
                {"input": "test"},
            )

        receipts = proxy.get_receipts()
        assert len(receipts) == 1
        assert receipts[0]["success"] is False
        assert "503" in (receipts[0]["error"] or "")

        await proxy.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_discover_remote_capabilities(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.OUTBOUND_ONLY
        )
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        respx.get(f"{PUBLIC_PEER.gateway_endpoint}/mcp/v1/tools").respond(
            json={
                "tools": [
                    {"name": "urn:coreason:actionspace:solver:test:v1"},
                    {"name": "urn:coreason:actionspace:oracle:data:v1"},
                ]
            },
        )

        caps = await proxy.discover_remote_capabilities(PUBLIC_PEER.instance_id)
        assert len(caps) == 2

        await proxy.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_discover_with_urn_filter(self) -> None:
        agreement = _make_private_to_public_agreement(
            direction=ConnectivityDirection.OUTBOUND_ONLY,
            allowed_urns=["urn:coreason:actionspace:solver:*"],
        )
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])

        respx.get(f"{PUBLIC_PEER.gateway_endpoint}/mcp/v1/tools").respond(
            json={
                "tools": [
                    {"name": "urn:coreason:actionspace:solver:test:v1"},
                    {"name": "urn:coreason:actionspace:oracle:data:v1"},
                ]
            },
        )

        caps = await proxy.discover_remote_capabilities(PUBLIC_PEER.instance_id)
        # Only solver should pass the filter
        assert len(caps) == 1
        assert "solver" in caps[0]["name"]

        await proxy.close()


# ---------------------------------------------------------------------------
# Audit receipt tests
# ---------------------------------------------------------------------------


class TestFederatedExecutionReceipt:
    """Tests for the audit receipt model."""

    def test_receipt_serialization(self) -> None:
        receipt = FederatedExecutionReceipt(
            receipt_id="test-001",
            agreement_id="agreement-001",
            source_instance="alpha",
            destination_instance="beta",
            urn="urn:coreason:test",
            payload_hash="abc123",
        )
        d = receipt.to_dict()
        assert d["receipt_id"] == "test-001"
        assert d["success"] is True
        assert d["error"] is None
        assert d["timestamp"] is not None

    def test_receipt_with_error(self) -> None:
        receipt = FederatedExecutionReceipt(
            receipt_id="test-002",
            agreement_id="agreement-001",
            source_instance="alpha",
            destination_instance="beta",
            urn="urn:coreason:test",
            payload_hash="abc123",
            success=False,
            error="Connection refused",
        )
        d = receipt.to_dict()
        assert d["success"] is False
        assert d["error"] == "Connection refused"


# ---------------------------------------------------------------------------
# DLP scanning tests
# ---------------------------------------------------------------------------


class TestDLPScanning:
    """Tests for the DLP payload scanning enforcement."""

    def test_small_payload_passes(self) -> None:
        result = FederationProxy._dlp_scan_outbound({"key": "value"})
        assert result == {"key": "value"}

    def test_oversized_payload_rejected(self) -> None:
        # Create a payload larger than 10MB
        huge = {"data": "x" * (10_485_761)}
        with pytest.raises(ValueError, match="10MB"):
            FederationProxy._dlp_scan_outbound(huge)

    def test_inbound_scan_passes_normal_response(self) -> None:
        result = FederationProxy._dlp_scan_inbound({"result": "ok"})
        assert result == {"result": "ok"}


# ---------------------------------------------------------------------------
# Ephemeral cert generation tests
# ---------------------------------------------------------------------------


class TestEphemeralCerts:
    """Tests for development-only ephemeral certificate generation."""

    def test_rejects_non_development_env(self) -> None:
        # Ensure we're not in development mode
        old = os.environ.pop("COREASON_ENV", None)
        try:
            with pytest.raises(RuntimeError, match="development"):
                FederationProxy.generate_ephemeral_certs()
        finally:
            if old:
                os.environ["COREASON_ENV"] = old

    def test_generates_valid_pem_in_dev_mode(self) -> None:
        os.environ["COREASON_ENV"] = "development"
        try:
            cert_pem, key_pem = FederationProxy.generate_ephemeral_certs()
            assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
            assert key_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
        finally:
            del os.environ["COREASON_ENV"]


# ---------------------------------------------------------------------------
# Receipt lifecycle tests
# ---------------------------------------------------------------------------


class TestReceiptLifecycle:
    """Tests for receipt storage and cleanup."""

    def test_clear_receipts(self) -> None:
        proxy = FederationProxy(local_instance=PRIVATE_PEER)
        # Manually add a receipt
        proxy._receipts.append(
            FederatedExecutionReceipt(
                receipt_id="test",
                agreement_id="test",
                source_instance="a",
                destination_instance="b",
                urn="urn:coreason:test",
                payload_hash="abc",
            )
        )
        assert len(proxy.get_receipts()) == 1
        cleared = proxy.clear_receipts()
        assert cleared == 1
        assert len(proxy.get_receipts()) == 0


# ---------------------------------------------------------------------------
# Canonical Public identity tests
# ---------------------------------------------------------------------------


class TestCanonicalPublicIdentity:
    """Tests for the canonical CoReason Public network identity."""

    def test_create_public_peer_returns_correct_identity(self) -> None:
        from coreason_ecosystem.federation.proxy import (
            COREASON_PUBLIC_INSTANCE_ID,
            COREASON_PUBLIC_SPIFFE_DOMAIN,
            COREASON_PUBLIC_TENANT_CID,
            create_public_peer,
        )

        peer = create_public_peer()
        assert peer.instance_id == COREASON_PUBLIC_INSTANCE_ID
        assert peer.instance_type == InstanceType.PUBLIC
        assert peer.spiffe_trust_domain == COREASON_PUBLIC_SPIFFE_DOMAIN
        assert peer.tenant_cid == COREASON_PUBLIC_TENANT_CID
        assert peer.clearance == "PUBLIC"

    def test_there_is_exactly_one_public_network(self) -> None:
        from coreason_ecosystem.federation.proxy import (
            COREASON_PUBLIC_INSTANCE_ID,
            create_public_peer,
        )

        p1 = create_public_peer()
        p2 = create_public_peer()
        assert p1.instance_id == p2.instance_id == COREASON_PUBLIC_INSTANCE_ID


# ---------------------------------------------------------------------------
# Mode flipping tests
# ---------------------------------------------------------------------------


class TestInstanceModeFlipping:
    """Tests for flipping an instance between PRIVATE and PUBLIC mode."""

    def test_initial_mode(self) -> None:
        proxy = FederationProxy(local_instance=PRIVATE_PEER)
        assert proxy.instance_mode == InstanceType.PRIVATE

    def test_flip_private_to_public(self) -> None:
        proxy = FederationProxy(local_instance=PRIVATE_PEER)
        proxy.set_instance_mode(InstanceType.PUBLIC)
        assert proxy.instance_mode == InstanceType.PUBLIC

    def test_flip_public_to_private_is_prohibited(self) -> None:
        proxy = FederationProxy(local_instance=PUBLIC_PEER)
        with pytest.raises(ValueError, match="PUBLIC to PRIVATE"):
            proxy.set_instance_mode(InstanceType.PRIVATE)

    def test_flip_clears_cached_clients(self) -> None:
        proxy = FederationProxy(local_instance=PRIVATE_PEER)
        # Simulate a cached client
        proxy._clients["test-peer"] = httpx.AsyncClient()
        assert len(proxy._clients) == 1

        proxy.set_instance_mode(InstanceType.PUBLIC)
        assert len(proxy._clients) == 0

    def test_flip_preserves_agreements(self) -> None:
        agreement = _make_private_to_public_agreement()
        proxy = FederationProxy(local_instance=PRIVATE_PEER, agreements=[agreement])
        # Agreement is registered
        assert PUBLIC_PEER.instance_id in proxy._agreements

        proxy.set_instance_mode(InstanceType.PUBLIC)
        # Agreements still registered after mode flip
        assert PUBLIC_PEER.instance_id in proxy._agreements


# ---------------------------------------------------------------------------
# Contribution Governance tests (Private → Public publishing RBAC)
# ---------------------------------------------------------------------------


def _make_contribution_policy(
    enabled: bool = True,
    required_approvals: int = 2,
    allowed_urns: list[str] | None = None,
) -> ContributionPolicy:
    return ContributionPolicy(
        enabled=enabled,
        required_approvals=required_approvals,
        allowed_contribution_urns=allowed_urns or ["urn:coreason:actionspace:solver:*"],
    )


def _make_contribution_intent(
    intent_id: str = "contrib-001",
    urn: str = "urn:coreason:actionspace:solver:nlp_extractor:v1",
    legal_attestation: bool = True,
) -> ContributionIntent:
    return ContributionIntent(
        intent_id=intent_id,
        urn=urn,
        contributor_id="spiffe://alpha.internal/ns/eng/sa/jane.doe",
        justification="Contributing NLP extractor for community use.",
        legal_attestation=legal_attestation,
    )


class TestContributionPolicy:
    """Tests for ContributionPolicy model defaults and validation."""

    def test_disabled_by_default(self) -> None:
        policy = ContributionPolicy()
        assert policy.enabled is False
        assert policy.required_approvals == 2
        assert policy.allowed_contribution_urns == []
        assert policy.max_contribution_clearance == "PUBLIC"

    def test_urns_are_canonically_sorted(self) -> None:
        policy = ContributionPolicy(
            allowed_contribution_urns=[
                "urn:coreason:z:*",
                "urn:coreason:a:*",
            ]
        )
        assert policy.allowed_contribution_urns == [
            "urn:coreason:a:*",
            "urn:coreason:z:*",
        ]


class TestContributionGovernance:
    """Tests for the full contribution RBAC workflow."""

    def test_submit_requires_private_instance(self) -> None:
        proxy = FederationProxy(
            local_instance=PUBLIC_PEER,
            contribution_policy=_make_contribution_policy(),
        )
        intent = _make_contribution_intent()
        with pytest.raises(PermissionError, match="PRIVATE"):
            proxy.submit_contribution(intent)

    def test_submit_requires_enabled_policy(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(enabled=False),
        )
        intent = _make_contribution_intent()
        with pytest.raises(PermissionError, match="disabled"):
            proxy.submit_contribution(intent)

    def test_submit_requires_allowed_urn(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(
                allowed_urns=["urn:coreason:actionspace:oracle:*"],
            ),
        )
        # Solver URN does not match oracle pattern
        intent = _make_contribution_intent()
        with pytest.raises(PermissionError, match="not in the allowed"):
            proxy.submit_contribution(intent)

    def test_submit_requires_legal_attestation(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(),
        )
        intent = _make_contribution_intent(legal_attestation=False)
        with pytest.raises(PermissionError, match="Legal attestation"):
            proxy.submit_contribution(intent)

    def test_submit_succeeds_with_valid_intent(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(),
        )
        intent = _make_contribution_intent()
        result = proxy.submit_contribution(intent)
        assert result.status == "PENDING"
        assert len(proxy.get_contribution_intents()) == 1

    def test_approve_enforces_separation_of_duties(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(),
        )
        intent = _make_contribution_intent()
        proxy.submit_contribution(intent)

        # Contributor cannot approve their own intent
        with pytest.raises(PermissionError, match="Separation of duties"):
            proxy.approve_contribution(
                "contrib-001",
                "spiffe://alpha.internal/ns/eng/sa/jane.doe",
            )

    def test_approve_prevents_duplicate(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(),
        )
        intent = _make_contribution_intent()
        proxy.submit_contribution(intent)

        approver = "spiffe://alpha.internal/ns/security/sa/bob.smith"
        proxy.approve_contribution("contrib-001", approver)

        with pytest.raises(PermissionError, match="already approved"):
            proxy.approve_contribution("contrib-001", approver)

    def test_multi_party_approval_workflow(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(required_approvals=2),
        )
        intent = _make_contribution_intent()
        proxy.submit_contribution(intent)

        # First approval — still PENDING
        result = proxy.approve_contribution(
            "contrib-001",
            "spiffe://alpha.internal/ns/security/sa/bob.smith",
        )
        assert result.status == "PENDING"

        # Second approval — now APPROVED
        result = proxy.approve_contribution(
            "contrib-001",
            "spiffe://alpha.internal/ns/governance/sa/alice.jones",
        )
        assert result.status == "APPROVED"
        assert len(result.approvals) == 2

    def test_rejection_workflow(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(),
        )
        intent = _make_contribution_intent()
        proxy.submit_contribution(intent)

        result = proxy.reject_contribution(
            "contrib-001",
            "spiffe://alpha.internal/ns/security/sa/bob.smith",
            "Contains references to internal patient IDs.",
        )
        assert result.status == "REJECTED"

    @pytest.mark.asyncio
    async def test_execute_requires_approved_status(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=_make_contribution_policy(),
        )
        intent = _make_contribution_intent()
        proxy.submit_contribution(intent)

        with pytest.raises(ValueError, match="not APPROVED"):
            await proxy.execute_contribution("contrib-001")

    def test_intent_hash_is_deterministic(self) -> None:
        intent = _make_contribution_intent()
        h1 = intent.compute_intent_hash()
        h2 = intent.compute_intent_hash()
        assert h1 == h2
        assert len(h1) == 64

    def test_empty_allowed_urns_blocks_all(self) -> None:
        proxy = FederationProxy(
            local_instance=PRIVATE_PEER,
            contribution_policy=ContributionPolicy(
                enabled=True,
                allowed_contribution_urns=[],
            ),
        )
        intent = _make_contribution_intent()
        with pytest.raises(PermissionError, match="No URN patterns"):
            proxy.submit_contribution(intent)

    @pytest.mark.asyncio
    async def test_absorb_remote_capability_public_mesh_only(self) -> None:
        # Cannot absorb if Private
        proxy_private = FederationProxy(local_instance=PRIVATE_PEER)
        with pytest.raises(PermissionError, match="can only be executed by a PUBLIC"):
            await proxy_private.absorb_remote_capability("peer-123", {})

        # Can absorb if Public
        proxy_public = FederationProxy(local_instance=PUBLIC_PEER)
        # Add a mock private peer to the registry so handshake passes
        agreement = _make_private_to_public_agreement()
        proxy_public.register_agreement(agreement)

        payload = {
            "urn": "urn:coreason:actionspace:solver:test_solver:v1",
            "legal_attestation": {"agrees_to_public_release": True},
            "intent_hash": "mockhash",
        }

        result = await proxy_public.absorb_remote_capability(
            PRIVATE_PEER.instance_id, payload
        )
        assert result["status"] == "absorbed"
        assert result["urn"] == "urn:coreason:actionspace:solver:test_solver:v1"
        assert result["provider_instance"] == PRIVATE_PEER.instance_id

    @pytest.mark.asyncio
    async def test_absorb_remote_capability_rejects_missing_attestation(self) -> None:
        proxy_public = FederationProxy(local_instance=PUBLIC_PEER)
        agreement = _make_private_to_public_agreement()
        proxy_public.register_agreement(agreement)

        payload = {
            "urn": "urn:coreason:actionspace:solver:test_solver:v1",
            "legal_attestation": {"agrees_to_public_release": False},
        }

        with pytest.raises(PermissionError, match="Missing legal attestation"):
            await proxy_public.absorb_remote_capability(
                PRIVATE_PEER.instance_id, payload
            )
