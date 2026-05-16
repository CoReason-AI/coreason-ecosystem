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


def test_semantic_router_missing_arrow_matrix(tmp_path: Path) -> None:
    router = SemanticRouter(tmp_path / "missing.arrow")
    assert len(router.registry) == 0


def test_semantic_router_corrupted_arrow_matrix(tmp_path: Path) -> None:
    corrupted_path = tmp_path / "corrupted.arrow"
    with open(corrupted_path, "wb") as f:
        f.write(b"this is not a valid arrow file")

    with pytest.raises(
        RuntimeError, match="Cannot initialize SemanticRouter: Matrix corrupted"
    ):
        SemanticRouter(corrupted_path)


def test_configure_routellm_empty_target_models(dummy_arrow_matrix: Path) -> None:
    router = SemanticRouter(dummy_arrow_matrix)
    config = router.configure_routellm([], 0.75)

    assert config["router"] == "routellm"
    assert config["threshold"] == 0.75
    assert config["models"] == []
    assert config["capabilities_mapped"] == 2
