from datetime import datetime, timedelta, timezone
from pathlib import Path

from ledgerly.core.yamlio import read_yaml
from ledgerly.core.yamlio import write_yaml
from ledgerly.engine.claims import (
    add_claim,
    citation_gap_claims,
    claim_source_validation_report,
    list_claims,
    set_claim_status,
    stale_claims,
    write_citation_gap_report,
    write_stale_claims_report,
)
from ledgerly.engine.workspace import init_workspace


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


def test_stale_claims_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    fresh = add_claim(workspace, text="Fresh claim", linked_sources=["source-001"])
    old_gap = add_claim(workspace, text="Old unsupported claim")
    old_supported = add_claim(workspace, text="Old but resolved claim", linked_sources=["source-001"])
    legacy = add_claim(workspace, text="Legacy claim with no timestamps", linked_sources=["source-001"])

    old_iso = (datetime.now(timezone.utc) - timedelta(days=20)).replace(microsecond=0).isoformat()
    ledger_path = workspace / "claims-ledger.yaml"
    ledger = read_yaml(ledger_path)
    for claim in ledger["claims"]:
        if claim["id"] == old_gap["id"]:
            claim["created_at"] = claim["updated_at"] = old_iso
        elif claim["id"] == old_supported["id"]:
            claim["created_at"] = claim["updated_at"] = old_iso
            claim["status"] = "supported"
        elif claim["id"] == legacy["id"]:
            claim.pop("created_at", None)
            claim.pop("updated_at", None)
    write_yaml(ledger_path, ledger)

    stale = stale_claims(workspace, days=14)
    stale_ids = {claim["id"] for claim in stale}

    assert fresh["id"] not in stale_ids
    assert old_gap["id"] in stale_ids
    assert old_supported["id"] not in stale_ids
    assert legacy["id"] in stale_ids

    gap_entry = next(claim for claim in stale if claim["id"] == old_gap["id"])
    assert gap_entry["is_citation_gap"] is True
    assert gap_entry["age_days"] == 20

    legacy_entry = next(claim for claim in stale if claim["id"] == legacy["id"])
    assert legacy_entry["age_days"] is None
    assert legacy_entry["is_citation_gap"] is False

    output_path = write_stale_claims_report(workspace, days=14)
    report = read_yaml(output_path)
    assert report["days_threshold"] == 14
    assert report["stale_count"] == 2
    assert report["citation_gap_count"] == 1
