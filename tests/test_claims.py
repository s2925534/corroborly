from pathlib import Path

from researchboss.core.yamlio import read_yaml
from researchboss.core.yamlio import write_yaml
from researchboss.engine.claims import (
    add_claim,
    citation_gap_claims,
    claim_source_validation_report,
    list_claims,
    set_claim_status,
    write_citation_gap_report,
)
from researchboss.engine.workspace import init_workspace


def test_claim_ledger_and_citation_gap_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    supported = add_claim(workspace, text="Supported claim", linked_sources=["source-001"])
    unsupported = add_claim(workspace, text="Unsupported claim")
    output_path = write_citation_gap_report(workspace)

    assert supported["id"] == "claim-001"
    assert unsupported["id"] == "claim-002"
    assert [claim["id"] for claim in list_claims(workspace)] == ["claim-001", "claim-002"]
    assert [claim["id"] for claim in citation_gap_claims(workspace)] == ["claim-002"]
    report = read_yaml(output_path)
    assert report["gap_count"] == 1
    assert report["claims"][0]["text"] == "Unsupported claim"


def test_claim_status_and_source_validation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    write_yaml(
        workspace / "source-register.yaml",
        {"version": 1, "sources": [{"source_id": "source-001", "status": "maybe"}]},
    )
    claim = add_claim(workspace, text="Claim", linked_sources=["source-001"])

    set_claim_status(workspace, claim["id"], "needs_evidence")
    report = claim_source_validation_report(workspace)

    assert list_claims(workspace)[0]["status"] == "needs_evidence"
    assert report["claims"][0]["status"] == "needs_review"
    assert report["claims"][0]["issues"][0]["kind"] == "source_not_accepted"
