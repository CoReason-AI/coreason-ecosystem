# Copyright (c) 2026 CoReason, Inc.
"""
Tests for the Hollow Semantic Router.

These tests validate the behavior of the router as an RPC client delegating
to the coreason-runtime discovery API.
"""

import pytest
import respx
from httpx import Response
from coreason_ecosystem.gateway.semantic_router import (
    SemanticRouter,
    IntentWeighting,
    HybridWeighting,
    ScoreCalibration,
)


@pytest.fixture
def router() -> SemanticRouter:
    return SemanticRouter(runtime_url="http://test-runtime:8000")


@pytest.mark.asyncio
async def test_route_intent_success(router: SemanticRouter) -> None:
    async with respx.mock:
        respx.post("http://test-runtime:8000/api/v1/discovery/search").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "name": "urn:coreason:actionspace:solver:data_extract:v1",
                        "description": "Extract data",
                        "inputSchema": {"type": "object"},
                        "distance": 0.1,
                    }
                ],
            )
        )

        results = await router.route_intent("extract data from PDF", limit=1)

        assert len(results) == 1
        assert results[0] == "urn:coreason:actionspace:solver:data_extract:v1"


@pytest.mark.asyncio
async def test_route_intent_failure_graceful(router: SemanticRouter) -> None:
    async with respx.mock:
        respx.post("http://test-runtime:8000/api/v1/discovery/search").mock(
            return_value=Response(500)
        )

        results = await router.route_intent("extract data from PDF")

        assert results == []


@pytest.mark.asyncio
async def test_route_intent_unreachable_graceful(router: SemanticRouter) -> None:
    # No respx mock -> unreachable
    results = await router.route_intent("extract data from PDF")
    assert results == []


def test_legacy_stubs() -> None:
    # Verify legacy classes exist and can be instantiated without error
    iw = IntentWeighting(w_inst=0.5)
    sc = ScoreCalibration(holistic_exponent=2.0)
    hw = HybridWeighting(w_holistic=0.5, w_wells=0.5, calibration=sc)
    assert iw is not None
    assert sc is not None
    assert hw is not None


@pytest.mark.asyncio
async def test_router_close(router: SemanticRouter) -> None:
    await router.close()
    # The client should be closed
    assert router._client.is_closed
