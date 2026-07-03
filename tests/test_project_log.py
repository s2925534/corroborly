from pathlib import Path

from researchboss.core.yamlio import read_yaml
from researchboss.engine.project_log import (
    add_context_change,
    add_decision,
    add_feedback,
    add_terminology,
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
