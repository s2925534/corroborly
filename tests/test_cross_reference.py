from pathlib import Path

import pytest

from researchboss.core.yamlio import write_yaml
from researchboss.engine.claims import add_claim
from researchboss.engine.artefacts import register_artefact
from researchboss.engine.cross_reference import cross_reference_candidates
from researchboss.engine.vault import intake_uploaded_artefact
from researchboss.engine.workspace import init_workspace


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    return workspace


def test_cross_reference_candidates_matches_artefact_by_title_overlap(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "berth-planning-notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Notes")

    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    register_artefact(workspace, title="Berth Planning Summary", artefact_type="report", path=artefact_path)

    report = cross_reference_candidates(workspace, upload["upload_id"])

    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["target_kind"] == "artefact"
    assert "berth" in candidate["matched_keywords"]
    assert "planning" in candidate["matched_keywords"]
    assert report["links_written"] is False


def test_cross_reference_candidates_matches_source_by_title_overlap(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "container-automation.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Container Automation Draft")

    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "file_name": "paper.pdf",
                    "citation_metadata": {"title": "Container Terminal Automation Evidence"},
                }
            ],
        },
    )

    report = cross_reference_candidates(workspace, upload["upload_id"])

    source_candidates = [c for c in report["candidates"] if c["target_kind"] == "source"]
    assert len(source_candidates) == 1
    assert source_candidates[0]["target_id"] == "source-001"
    assert "container" in source_candidates[0]["matched_keywords"]


def test_cross_reference_candidates_requires_stronger_overlap_for_claims(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth")  # single keyword only

    add_claim(workspace, text="Berth planning improves container throughput significantly.")

    report = cross_reference_candidates(workspace, upload["upload_id"])

    claim_candidates = [c for c in report["candidates"] if c["target_kind"] == "claim"]
    assert claim_candidates == []  # only one shared keyword ("berth"), below the claim threshold


def test_cross_reference_candidates_matches_claims_with_enough_overlap(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Automation")

    add_claim(workspace, text="Berth planning automation improves throughput.")

    report = cross_reference_candidates(workspace, upload["upload_id"])

    claim_candidates = [c for c in report["candidates"] if c["target_kind"] == "claim"]
    assert len(claim_candidates) == 1


def test_cross_reference_candidates_never_writes_links_only_a_report(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Some Notes")

    report = cross_reference_candidates(workspace, upload["upload_id"])

    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload['upload_id']}.yaml"
    assert report_path.is_file()
    assert report["links_written"] is False


def test_cross_reference_candidates_rejects_unknown_upload_id(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    with pytest.raises(ValueError, match="Unknown upload_id"):
        cross_reference_candidates(workspace, "upload-999")
