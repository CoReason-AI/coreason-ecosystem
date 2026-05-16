import pyarrow as pa
from pathlib import Path
import pytest

from coreason_ecosystem.gateway.semantic_router import SemanticRouter


@pytest.fixture
def dummy_arrow_matrix(tmp_path: Path) -> Path:
    arrow_path = tmp_path / "matrix.arrow"

    dummy_data = [
        {
            "urn": "urn:coreason:actionspace:solver:data_extract:v1",
            "congruence_score": 0.95,
        },
        {
            "urn": "urn:coreason:actionspace:effector:write_db:v1",
            "congruence_score": 0.90,
        },
    ]

    table = pa.Table.from_pylist(dummy_data)
    with pa.OSFile(str(arrow_path), "wb") as sink:
        with pa.RecordBatchFileWriter(sink, table.schema) as writer:
            writer.write_table(table)

    return arrow_path


def test_semantic_router_loads_arrow(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)
    assert len(router.registry) == 2
    assert (
        router.registry[0]["urn"] == "urn:coreason:actionspace:solver:data_extract:v1"
    )


def test_generate_envoy_configuration(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)
    config = router.generate_envoy_configuration()

    assert "routes" in config
    assert len(config["routes"]) == 2

    route0 = config["routes"][0]
    assert (
        route0["match"]["headers"][0]["exact_match"]
        == "urn:coreason:actionspace:solver:data_extract:v1"
    )
    assert route0["route"]["cluster"] == "routellm_cluster"


def test_configure_routellm(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)
    config = router.configure_routellm(["gpt-4", "llama-3"], 0.75)

    assert config["router"] == "routellm"
    assert config["threshold"] == 0.75
    assert config["models"] == ["gpt-4", "llama-3"]
    assert config["capabilities_mapped"] == 2
