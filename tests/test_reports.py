from pathlib import Path

from researchboss.engine.claims import add_claim
from researchboss.engine.report_schemas import export_report_schemas
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


def test_export_report_schemas_writes_yaml_and_markdown_guidance(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="Local evidence")

    result = export_report_schemas(workspace)

    yaml_text = result.yaml_path.read_text(encoding="utf-8")
    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert result.schema_count == 5
    assert "document_validation" in yaml_text
    assert "citation_insertion_plan" in yaml_text
    assert "APA7 is the default" in markdown
