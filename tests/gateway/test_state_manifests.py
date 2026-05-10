import pytest
from pydantic import ValidationError

from coreason_ecosystem.gateway.state_manifests import CapabilityEntry, CapabilityMatrix


def test_capability_entry_valid() -> None:
    entry = CapabilityEntry(
        urn="urn:coreason:actionspace:oracle:foo",
        endpoint="http://foo-service:8000",
        clearance="CONFIDENTIAL",
        epistemic_status="PUBLISHED",
    )
    assert entry.urn == "urn:coreason:actionspace:oracle:foo"
    assert entry.endpoint == "http://foo-service:8000"
    assert entry.clearance == "CONFIDENTIAL"
    assert entry.epistemic_status == "PUBLISHED"


def test_capability_entry_defaults() -> None:
    entry = CapabilityEntry(
        urn="urn:coreason:archetype_a:storage:bar", endpoint="http://bar-service:8000"
    )
    assert entry.clearance == "RESTRICTED"
    assert entry.epistemic_status == "DRAFT"


def test_capability_entry_invalid_urn_pattern() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CapabilityEntry(urn="invalid:urn:pattern", endpoint="http://foo:8000")
    assert "String should match pattern" in str(exc_info.value)


def test_capability_entry_invalid_clearance() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CapabilityEntry(
            urn="urn:coreason:actionspace:node:x",
            endpoint="http://x:8000",
            clearance="SECRET",
        )
    assert "Input should be 'PUBLIC', 'CONFIDENTIAL' or 'RESTRICTED'" in str(
        exc_info.value
    )


def test_capability_entry_invalid_epistemic_status() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CapabilityEntry(
            urn="urn:coreason:actionspace:node:x",
            endpoint="http://x:8000",
            epistemic_status="APPROVED",
        )
    assert (
        "Input should be 'DRAFT', 'SRB_APPROVED', 'CLIENT_APPROVED' or 'PUBLISHED'"
        in str(exc_info.value)
    )


def test_capability_matrix_valid() -> None:
    matrix = CapabilityMatrix(
        capabilities=[
            CapabilityEntry(
                urn="urn:coreason:oracle:legacy",
                endpoint="http://legacy:8000",
                clearance="PUBLIC",
                epistemic_status="SRB_APPROVED",
            ),
            {
                "urn": "urn:coreason:actionspace:sensory:vision",
                "endpoint": "http://vision:8000",
                "clearance": "RESTRICTED",
                "epistemic_status": "DRAFT",
            },
        ]
    )
    assert len(matrix.capabilities) == 2
    assert matrix.capabilities[1].urn == "urn:coreason:actionspace:sensory:vision"


def test_capability_matrix_empty() -> None:
    matrix = CapabilityMatrix()
    assert matrix.capabilities == []
