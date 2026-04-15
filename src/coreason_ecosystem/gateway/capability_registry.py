class CapabilityRegistry:
    """
    Physical mapping module linking URN boundaries to deployed action spaces.
    """

    CLEARANCE_LEVELS = {
        "PUBLIC": 1,
        "CONFIDENTIAL": 2,
        "RESTRICTED": 3,
    }

    def __init__(self) -> None:
        """Initialize the capability registry."""
        self._cache: dict[str, dict[str, str]] = {
            "urn:coreason:oracle:clinical_extractor": {
                "endpoint": "http://svc-pubmed-mcp.internal:8000",
                "clearance": "PUBLIC",
            },
            "urn:coreason:oracle:mathematics": {
                "endpoint": "http://svc-math-mcp.internal:8000",
                "clearance": "CONFIDENTIAL",
            },
            "urn:coreason:oracle:weapon_systems": {
                "endpoint": "http://svc-weapons-mcp.internal:8000",
                "clearance": "RESTRICTED",
            },
        }

    async def discover_active_substrates(
        self, agent_clearance: str = "PUBLIC"
    ) -> dict[str, str]:
        """
        Interrogates cluster telemetry to resolve available subsystems.
        Applies epistemic masking based on the agent's clearance.

        Args:
            agent_clearance: The semantic clearance of the requesting agent.

        Returns:
            A mapping of URN strings to physical network actionSpaceId URIs.
        """
        agent_level = self.CLEARANCE_LEVELS.get(agent_clearance, 0)

        masked_substrates: dict[str, str] = {}
        for urn, data in self._cache.items():
            required_clearance = data.get("clearance", "RESTRICTED")
            required_level = self.CLEARANCE_LEVELS.get(required_clearance, 3)

            if agent_level >= required_level:
                masked_substrates[urn] = data["endpoint"]

        return masked_substrates

    def resolve_urn(self, target_urn: str) -> str:
        """
        Strict physical lookup over the active substrates.

        Args:
            target_urn: The URN of the capability to resolve.

        Returns:
            The mapped physical endpoint URI.

        Raises:
            KeyError: if the target_urn is not in the registry.
        """
        if target_urn not in self._cache:
            raise KeyError(f"Geometrical topology fault: unregistered URN {target_urn}")

        return self._cache[target_urn]["endpoint"]
