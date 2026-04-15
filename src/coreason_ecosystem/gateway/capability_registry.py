class CapabilityRegistry:
    """
    Physical mapping module linking URN boundaries to deployed action spaces.
    """

    def __init__(self) -> None:
        """Initialize the capability registry."""
        self._cache: dict[str, str] = {
            "urn:coreason:oracle:clinical_extractor": "http://svc-pubmed-mcp.internal:8000",
            "urn:coreason:oracle:mathematics": "http://svc-math-mcp.internal:8000",
        }

    async def discover_active_substrates(self) -> dict[str, str]:
        """
        Interrogates cluster telemetry to resolve available subsystems.

        Returns:
            A mapping of URN strings to physical network actionSpaceId URIs.
        """
        # Simulated lookup representing a cluster state interrogator.
        return self._cache

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

        return self._cache[target_urn]
