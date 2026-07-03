from pathlib import Path

import pytest

from researchboss.engine.guidelines import list_guidelines, register_guideline
from researchboss.engine.workspace import init_workspace


def test_register_guideline_snapshots_local_text_without_modifying_original(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = tmp_path / "rubric.txt"
    source.write_text("Use APA7 references.\nCheck claim evidence.\n", encoding="utf-8")
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = register_guideline(workspace, str(source), title="Faculty Rubric")

    assert result.record["id"] == "guideline-001"
    assert result.record["title"] == "Faculty Rubric"
    assert result.record["source_kind"] == "local_file"
    assert result.record["scopes"] == ["all_purpose"]
    assert result.snapshot_path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert result.text_path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert source.read_text(encoding="utf-8") == "Use APA7 references.\nCheck claim evidence.\n"
    assert list_guidelines(workspace)[0]["id"] == "guideline-001"


def test_register_guideline_extracts_html_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = tmp_path / "journal.html"
    source.write_text("<html><body><h1>Rules</h1><p>Use structured abstracts.</p></body></html>", encoding="utf-8")
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = register_guideline(workspace, str(source), scopes=["journal-submission", "style"])

    text = result.text_path.read_text(encoding="utf-8")
    assert "Rules" in text
    assert "Use structured abstracts." in text
    assert result.record["scopes"] == ["journal_submission", "style"]


def test_register_guideline_rejects_unknown_scope(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = tmp_path / "rubric.txt"
    source.write_text("Rules", encoding="utf-8")
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    with pytest.raises(ValueError, match="Invalid guideline scope"):
        register_guideline(workspace, str(source), scopes=["unknown"])
