from pathlib import Path

from researchboss.engine.claims import add_claim
from researchboss.engine.reports import generate_workspace_report
from researchboss.engine.workspace import init_workspace


def test_generate_workspace_report_writes_markdown_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="Local evidence")
    add_claim(workspace, text="Unsupported claim")

    output_path = generate_workspace_report(workspace)

    text = output_path.read_text(encoding="utf-8")
    assert "# ResearchBoss Report: Test Project" in text
    assert "- Type: M.Phil" in text
    assert "- Citation gaps: 1" in text
