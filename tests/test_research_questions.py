from pathlib import Path

import pytest

from ledgerly.core.yamlio import read_yaml
from ledgerly.engine.research_questions import (
    add_research_question_candidate,
    assess_research_question_readiness,
    check_research_question_readiness,
    approve_research_question,
    archive_research_question,
    compose_research_question,
    list_research_questions,
    reject_research_question,
    split_candidate_relations,
)
from ledgerly.engine.workspace import init_workspace


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="PhD",
        topic="",
        research_questions=[
            {"question": "Approved question?", "status": "approved", "subquestions": []},
            {"question": "Draft question?", "status": "draft", "subquestions": ["Sub?"]},
        ],
    )
    return workspace


def test_approve_research_question_moves_candidate_to_approved(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    approve_research_question(workspace, "rq-002")

    groups = list_research_questions(workspace)
    assert [item["id"] for item in groups["approved"]] == ["rq-001", "rq-002"]
    assert groups["candidates"] == []


def test_reject_and_archive_research_questions(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    reject_research_question(workspace, "rq-002", reason="Too broad")
    archive_research_question(workspace, "rq-001", reason="Superseded")

    rejected = read_yaml(workspace / "rejected-research-questions.yaml")["rejected"]
    assert rejected[0]["status"] == "rejected"
    assert rejected[0]["reason"] == "Too broad"
    assert rejected[1]["status"] == "archived"
    assert rejected[1]["reason"] == "Superseded"


def test_approve_research_question_rejects_unknown_id(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    with pytest.raises(ValueError, match="Unknown candidate"):
        approve_research_question(workspace, "rq-999")


def test_assess_research_question_readiness_flags_scope_without_claiming_strength() -> None:
    result = assess_research_question_readiness(
        "What is the impact of things and how can it be better?",
        project_type="PhD",
    )

    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] in {"possibly_multiple_questions", "needs_scope"}
    assert "possibly_multiple_questions" in codes
    assert "vague_terms" in codes
    assert "novelty assessment" in result["ai_required_for_higher_certainty"]
    assert "Does not validate novelty." in result["limits"]


def test_check_research_question_readiness_writes_report_and_updates_records(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    report = check_research_question_readiness(workspace)

    assert report["ai_used"] is False
    assert report["human_review_required"] is True
    assert report["checked_count"] == 2
    assert (workspace / "outputs" / "validation" / "research-question-readiness.yaml").is_file()
    groups = list_research_questions(workspace)
    assert groups["approved"][0]["readiness"]["checked_by"] == "deterministic_rules"
    assert groups["candidates"][0]["readiness"]["human_review_required"] is True


def test_check_research_question_readiness_rejects_unknown_id(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    with pytest.raises(ValueError, match="Unknown research question"):
        check_research_question_readiness(workspace, rq_id="rq-999")


def test_compose_research_question_uses_type_specific_stem() -> None:
    assert compose_research_question("container automation reduces turnaround time", "Asian ports", "causal") == (
        "To what extent does container automation reduces turnaround time in Asian ports?"
    )
    assert compose_research_question("turnaround time between automated and manual terminals", "", "comparative") == (
        "How does turnaround time between automated and manual terminals?"
    )


def test_compose_research_question_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="Invalid question_type"):
        compose_research_question("something", "somewhere", "speculative")


def test_split_candidate_relations_splits_multiple_angles() -> None:
    assert split_candidate_relations("automation, cost efficiency, and safety") == [
        "automation",
        "cost efficiency",
        "safety",
    ]
    assert split_candidate_relations("a single unsplit phrase") == ["a single unsplit phrase"]


def test_add_research_question_candidate_saves_through_existing_storage(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="PhD",
        topic="",
        research_questions=[{"question": "Existing draft?", "status": "draft"}],
    )

    record = add_research_question_candidate(
        workspace,
        "To what extent does container automation reduce turnaround time in Asian ports?",
        hypothesis="Container automation reduces turnaround time.",
        question_type="causal",
        proof_criteria="Automated terminals show statistically lower turnaround times than manual ones.",
        disproof_criteria="No significant difference or automated terminals are slower.",
    )

    assert record["id"] == "rq-002"  # rq-001 already taken by the init-time draft
    assert record["status"] == "draft"
    groups = list_research_questions(workspace)
    assert groups["candidates"][-1]["id"] == "rq-002"
    assert groups["candidates"][-1]["hypothesis"] == "Container automation reduces turnaround time."
    assert groups["candidates"][-1]["question_type"] == "causal"

    # The rest of the RQ workflow works on it unchanged, no new storage path.
    check_research_question_readiness(workspace, rq_id="rq-002")
    approve_research_question(workspace, "rq-002")
    assert [item["id"] for item in list_research_questions(workspace)["approved"]] == ["rq-002"]


def test_add_research_question_candidate_rejects_empty_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    with pytest.raises(ValueError, match="required"):
        add_research_question_candidate(workspace, "   ")


def test_add_research_question_candidate_rejects_invalid_question_type(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    with pytest.raises(ValueError, match="Invalid question_type"):
        add_research_question_candidate(workspace, "A question?", question_type="speculative")
