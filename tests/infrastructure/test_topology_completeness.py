# Copyright (c) 2026 CoReason, Inc
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at <https://prosperitylicense.com/versions/3.0.0>
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: <https://github.com/CoReason-AI/coreason-ecosystem>

from pathlib import Path
import pytest
import yaml

# The Swarm Architecture Contract
# This matrix defines which macroscopic nodes require which backends.
# If a parent service is defined in a compose file, its backends MUST also be defined
# and correctly linked via `depends_on`.
TOPOLOGY_CONTRACT = {
    "nemoclaw": ["openshell-server"],
    "openshell-server": ["openshell-driver"],
    "coreason-master-gateway": ["coreason-runtime", "neo4j", "milvus", "vault"],
    "temporal": ["postgres"],
}


def get_compose_files():
    base_dir = Path(__file__).parent.parent.parent
    local_compose = base_dir / "infrastructure" / "local" / "compose.yaml"
    e2e_compose = base_dir / "tests" / "e2e_swarm" / "docker-compose.e2e.yaml"

    files = []
    if local_compose.exists():
        files.append(local_compose)
    if e2e_compose.exists():
        files.append(e2e_compose)
    return files


@pytest.mark.parametrize("compose_file", get_compose_files())
def test_topology_completeness(compose_file):
    with open(compose_file, "r") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})

    for service_name, config in services.items():
        if service_name in TOPOLOGY_CONTRACT:
            required_backends = TOPOLOGY_CONTRACT[service_name]
            for backend in required_backends:
                # 1. Assert backend is actually defined in the compose file
                assert backend in services, (
                    f"Topological Violation: '{service_name}' requires '{backend}', but it is missing from {compose_file.name}."
                )

                # 2. Assert depends_on linkage
                depends_on = config.get("depends_on", {})
                if isinstance(depends_on, list):
                    assert backend in depends_on, (
                        f"Topological Violation: '{service_name}' does not declare depends_on for '{backend}' in {compose_file.name}."
                    )
                elif isinstance(depends_on, dict):
                    assert backend in depends_on, (
                        f"Topological Violation: '{service_name}' does not declare depends_on for '{backend}' in {compose_file.name}."
                    )
