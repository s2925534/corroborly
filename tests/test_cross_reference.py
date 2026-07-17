from pathlib import Path

import pytest

from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.claims import add_claim
from ledgerly.engine.artefacts import register_artefact
from ledgerly.engine.cross_reference import (
    apply_cross_reference_links,
    cross_reference_candidates,
    set_cross_reference_candidate_review_status,
)
from ledgerly.engine.vault import intake_uploaded_artefact, list_uploaded_artefacts
from ledgerly.engine.workspace import init_workspace


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


def test_apply_cross_reference_links_writes_only_approved_candidates(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "berth-planning-notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Notes")

    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    register_artefact(workspace, title="Berth Planning Summary", artefact_type="report", path=artefact_path)
    add_claim(workspace, text="Berth planning improves throughput.")  # weaker match, left unapproved

    report = cross_reference_candidates(workspace, upload["upload_id"])
    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload['upload_id']}.yaml"
    report_data = read_yaml(report_path)
    # approve only the artefact candidate; leave any claim candidate untouched
    for candidate in report_data["candidates"]:
        if candidate["target_kind"] == "artefact":
            candidate["review_status"] = "accepted"
    write_yaml(report_path, report_data)

    result = apply_cross_reference_links(workspace, upload["upload_id"])

    assert result["applied_count"] == 1
    assert result["cross_references"][0]["target_kind"] == "artefact"
    uploaded = next(u for u in list_uploaded_artefacts(workspace) if u["upload_id"] == upload["upload_id"])
    assert uploaded["cross_references"] == result["cross_references"]
    # artefact/source/claim records themselves are never touched -- links live only on the upload
    updated_report = read_yaml(report_path)
    assert updated_report["links_written"] is True


def test_apply_cross_reference_links_does_not_duplicate_on_second_apply(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "berth-planning-notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Notes")
    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    register_artefact(workspace, title="Berth Planning Summary", artefact_type="report", path=artefact_path)

    cross_reference_candidates(workspace, upload["upload_id"])
    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload['upload_id']}.yaml"
    report_data = read_yaml(report_path)
    for candidate in report_data["candidates"]:
        candidate["review_status"] = "accepted"
    write_yaml(report_path, report_data)

    first = apply_cross_reference_links(workspace, upload["upload_id"])
    second = apply_cross_reference_links(workspace, upload["upload_id"])

    assert len(first["cross_references"]) == len(second["cross_references"]) == 1


def test_apply_cross_reference_links_requires_candidates_report_first(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Notes")

    with pytest.raises(ValueError, match="Run cross_reference_candidates first"):
        apply_cross_reference_links(workspace, upload["upload_id"])


def test_set_cross_reference_candidate_review_status_updates_one_candidate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "berth-planning-notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Notes")
    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    register_artefact(workspace, title="Berth Planning Summary", artefact_type="report", path=artefact_path)
    report = cross_reference_candidates(workspace, upload["upload_id"])
    candidate = report["candidates"][0]

    updated = set_cross_reference_candidate_review_status(
        workspace, upload["upload_id"], candidate["target_kind"], candidate["target_id"], "accepted"
    )

    assert updated["review_status"] == "accepted"
    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload['upload_id']}.yaml"
    persisted = read_yaml(report_path)
    assert persisted["candidates"][0]["review_status"] == "accepted"

    # applying now picks up the API-set status, same as a hand-edited file would
    result = apply_cross_reference_links(workspace, upload["upload_id"])
    assert result["applied_count"] == 1


def test_set_cross_reference_candidate_review_status_only_touches_matched_candidate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "berth-planning-notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Notes")
    for name in ("summary-one", "summary-two"):
        artefact_path = workspace / "artefacts" / "reports" / f"{name}.md"
        artefact_path.parent.mkdir(parents=True, exist_ok=True)
        artefact_path.write_text("# Summary", encoding="utf-8")
        register_artefact(workspace, title=f"Berth Planning {name}", artefact_type="report", path=artefact_path)
    report = cross_reference_candidates(workspace, upload["upload_id"])
    assert len(report["candidates"]) == 2
    first, second = report["candidates"]

    set_cross_reference_candidate_review_status(
        workspace, upload["upload_id"], first["target_kind"], first["target_id"], "accepted"
    )

    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload['upload_id']}.yaml"
    persisted = read_yaml(report_path)
    statuses = {c["target_id"]: c["review_status"] for c in persisted["candidates"]}
    assert statuses[first["target_id"]] == "accepted"
    assert statuses[second["target_id"]] == "needs_human_review"


def test_set_cross_reference_candidate_review_status_rejects_invalid_status(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "berth-planning-notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Notes")
    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    register_artefact(workspace, title="Berth Planning Summary", artefact_type="report", path=artefact_path)
    report = cross_reference_candidates(workspace, upload["upload_id"])
    candidate = report["candidates"][0]

    with pytest.raises(ValueError, match="Invalid review_status"):
        set_cross_reference_candidate_review_status(
            workspace, upload["upload_id"], candidate["target_kind"], candidate["target_id"], "maybe-later"
        )


def test_set_cross_reference_candidate_review_status_rejects_unknown_candidate(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Notes")
    cross_reference_candidates(workspace, upload["upload_id"])

    with pytest.raises(ValueError, match="No candidate found"):
        set_cross_reference_candidate_review_status(workspace, upload["upload_id"], "artefact", "bogus-id", "accepted")


def test_set_cross_reference_candidate_review_status_requires_candidates_report_first(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Notes")

    with pytest.raises(ValueError, match="Run cross_reference_candidates first"):
        set_cross_reference_candidate_review_status(workspace, upload["upload_id"], "artefact", "artefact-001", "accepted")


def test_ai_cross_reference_suggestions_returns_insufficient_evidence_without_calling_ai(tmp_path: Path) -> None:
    from ledgerly.engine.ai import OpenAiCredentials
    from ledgerly.engine.cross_reference import ai_cross_reference_suggestions

    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Notes")

    def opener(request):
        raise AssertionError("AI provider must not be called when there is no evidence to ground a response in")

    report = ai_cross_reference_suggestions(
        workspace, OpenAiCredentials(api_key="sk-secret"), upload["upload_id"], opener=opener
    )

    assert report["insufficient_evidence"] is True
    assert report["ai_used"] is False


def test_ai_cross_reference_suggestions_appends_validated_candidates_without_removing_deterministic_ones(
    tmp_path: Path,
) -> None:
    import json
    from ledgerly.engine.ai import OpenAiCredentials
    from ledgerly.engine.cross_reference import ai_cross_reference_suggestions

    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "berth-planning-notes.md"
    upload_source.write_text("notes", encoding="utf-8")
    upload = intake_uploaded_artefact(workspace, upload_source, title="Berth Planning Notes")

    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    register_artefact(workspace, title="Berth Planning Summary", artefact_type="report", path=artefact_path)
    claim = add_claim(workspace, text="Automation reduces turnaround time at container terminals.")

    cross_reference_candidates(workspace, upload["upload_id"])  # deterministic pass first

    class FakeResponse:
        def __init__(self, data):
            self.data = json.dumps(data).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.data

    def opener(request):
        return FakeResponse(
            {
                "id": "resp_xref",
                "output_text": (
                    f"### CANDIDATE target_kind=claim target_id={claim['id']}\n"
                    "RATIONALE: The upload discusses the same automation topic.\n"
                    "### END CANDIDATE\n"
                    "### CANDIDATE target_kind=artefact target_id=artefact-999\n"
                    "RATIONALE: A hallucinated artefact that does not exist.\n"
                    "### END CANDIDATE\n"
                ),
            }
        )

    report = ai_cross_reference_suggestions(
        workspace, OpenAiCredentials(api_key="sk-secret"), upload["upload_id"], opener=opener
    )

    assert report["ai_used"] is True
    assert report["ai_candidate_count"] == 1  # the hallucinated artefact-999 was dropped
    kinds_and_ids = {(c["target_kind"], c["target_id"]) for c in report["candidates"]}
    assert ("artefact", None) not in kinds_and_ids
    assert ("claim", claim["id"]) in kinds_and_ids
    # Original deterministic candidate (matched by title overlap) survives alongside the AI one.
    assert any(c["match_basis"] == "title_or_filename_keyword_overlap" for c in report["candidates"])
    assert any(c["match_basis"] == "ai_suggested" for c in report["candidates"])

    persisted = read_yaml(workspace / "outputs" / "recommendations" / f"cross-reference-{upload['upload_id']}.yaml")
    assert persisted["ai_candidate_count"] == 1
