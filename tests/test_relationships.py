from pathlib import Path

from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.artefacts import register_artefact
from ledgerly.engine.claims import add_claim
from ledgerly.engine.relationships import citation_relationship_map
from ledgerly.engine.workspace import init_workspace


def test_citation_relationship_map(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {"source_id": "source-001", "file_name": "paper-a.pdf", "status": "accepted"},
                {"source_id": "source-002", "file_name": "paper-b.pdf", "status": "accepted"},
            ],
        },
    )

    claim = add_claim(workspace, text="Container automation reduces turnaround time.", linked_sources=["source-001"])
    add_claim(workspace, text="Unsupported claim", linked_sources=[])
    artefact = register_artefact(
        workspace,
        title="Literature review",
        artefact_type="literature-review-matrix",
        path=Path("artefacts/reports/lit-review.md"),
        linked_sources=["source-001"],
    )

    report = citation_relationship_map(workspace)

    source_rows = {row["source_id"]: row for row in report["sources"]}
    assert "source-001" in source_rows
    assert "source-002" not in source_rows  # unreferenced source, excluded
    assert source_rows["source-001"]["claims"][0]["id"] == claim["id"]
    assert source_rows["source-001"]["artefacts"][0]["id"] == artefact["id"]

    claim_rows = {row["id"]: row for row in report["claims"]}
    assert claim_rows[claim["id"]]["sources"][0]["source_id"] == "source-001"
    assert claim_rows[claim["id"]]["sources"][0]["known"] is True

    artefact_rows = {row["id"]: row for row in report["artefacts"]}
    assert artefact_rows[artefact["id"]]["sources"][0]["source_id"] == "source-001"


def test_citation_relationship_map_flags_unknown_source(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    claim = add_claim(workspace, text="Claim citing a missing source", linked_sources=["source-999"])

    report = citation_relationship_map(workspace)

    claim_rows = {row["id"]: row for row in report["claims"]}
    ref = claim_rows[claim["id"]]["sources"][0]
    assert ref["source_id"] == "source-999"
    assert ref["known"] is False
    assert ref["file_name"] is None
