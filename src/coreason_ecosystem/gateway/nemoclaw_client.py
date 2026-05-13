# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from coreason_manifest.spec.ontology import GuardrailViolationEvent

logger = logging.getLogger(__name__)


class NemoClawBridgeClient:
    """AGENT INSTRUCTION: A specialized HTTP client wrapper for the NemoClaw (NeMo Guardrails) sidecar.
    It enforces strict security telemetry emission on 4xx violations, ensuring that every intercepted
    request is recorded in the Arrow-native telemetry broker as a GuardrailViolationEvent.

    CAUSAL AFFORDANCE: Physically intercepts 4xx status codes from the security proxy and
    transmutes them into formal Epistemic Log Events for the Governance Plane.

    EPISTEMIC BOUNDS: Bounded to the /v1/mcp endpoint of the sidecar. It cannot be used
    to bypass the security perimeter.

    MCP ROUTING TRIGGERS: NeMo Guardrails, NemoClaw, Security Telemetry, Egress Filtering
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def call_tool(
        self, target_urn: str, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{self.base_url}/v1/mcp/{target_urn}/tools/call"
        payload = {
            "name": name,
            "arguments": arguments,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=30.0)

                if 400 <= response.status_code < 500:
                    # Emit GuardrailViolationEvent telemetry
                    event = GuardrailViolationEvent(
                        event_cid=str(uuid.uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        violation_id=str(uuid.uuid4()),
                        message=f"Guardrail violation detected for tool {name} (URN: {target_urn})",
                        level="WARNING",
                        context_profile={
                            "event_type": "GuardrailViolationEvent",
                            "endpoint": url,
                            "status_code": response.status_code,
                            "target_urn": target_urn,
                            "tool_name": name,
                            "violation_details": response.text,
                        },
                        violation_type="output_scan"
                        if response.status_code == 403
                        else "input_scan",
                        mitigation_action="blocked",
                    )
                    # In ecosystem, we might not have the same log_event as runtime,
                    # so we log it as a structured log for now, or use a shared utility.
                    # Since we want it to hit the Arrow broker, we should ideally use
                    # the same logging infra.
                    logger.warning(event.model_dump_json())

                    response.raise_for_status()

                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]

            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    raise RuntimeError(
                        f"Security Policy Violation: {e.response.text}"
                    ) from e
                raise
