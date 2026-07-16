from pathlib import Path

from researchboss.core.yamlio import read_yaml
from researchboss.engine.project_log import (
    add_context_change,
    add_decision,
    add_feedback,
    add_terminology,
    list_context_changes,
    list_decisions,
    list_feedback,
    list_terminology,
    timeline_report,
)
from researchboss.engine.workspace import init_workspace


def test_project_log_commands_write_local_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    decision = add_decision(workspace, "Use accepted sources only", reason="Evidence boundary")
    term = add_terminology(workspace, "construct", "A concept being studied")
    feedback = add_feedback(workspace, "Narrow the scope", source="Supervisor")
    change = add_context_change(workspace, "Added deterministic logs")
    timeline = timeline_report(workspace)

    assert decision["id"] == "decision-001"
    assert term["term"] == "construct"
    assert feedback["id"] == "feedback-001"
    assert change["id"] == "change-001"
    assert "Use accepted sources only" in (workspace / "decisions.md").read_text(encoding="utf-8")
    assert read_yaml(workspace / "terminology.yaml")["terms"][0]["term"] == "construct"
    assert timeline["event_count"] >= 2
    assert (workspace / "outputs" / "reports" / "timeline.yaml").is_file()


def test_project_log_list_functions_read_back_structured_records(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    add_decision(workspace, "Use accepted sources only", reason="Evidence boundary")
    add_decision(workspace, "Prefer deterministic reports", reason="Avoid AI dependency")
    add_terminology(workspace, "construct", "A concept being studied")
    add_feedback(workspace, "Narrow the scope", source="Supervisor")
    add_context_change(workspace, "Added deterministic logs")
    add_context_change(workspace, "Second change\nwith a second line")

    decisions = list_decisions(workspace)
    assert decisions == [
        {"id": "decision-001", "decision": "Use accepted sources only", "reason": "Evidence boundary"},
        {"id": "decision-002", "decision": "Prefer deterministic reports", "reason": "Avoid AI dependency"},
    ]

    terms = list_terminology(workspace)
    assert terms == [{"term": "construct", "definition": "A concept being studied"}]

    feedback_items = list_feedback(workspace)
    assert feedback_items[0]["id"] == "feedback-001"
    assert feedback_items[0]["text"] == "Narrow the scope"

    changes = list_context_changes(workspace)
    assert changes[0] == {"id": "change-001", "text": "Added deterministic logs"}
    assert changes[1]["id"] == "change-002"
    assert "Second change" in changes[1]["text"]
    assert "with a second line" in changes[1]["text"]


def test_project_log_list_functions_empty_before_any_entries(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    assert list_decisions(workspace) == []
    assert list_terminology(workspace) == []
    assert list_feedback(workspace) == []
    assert list_context_changes(workspace) == []
