from pathlib import Path

import pytest

from researchboss.core.yamlio import read_yaml
from researchboss.engine.guidelines import (
    list_guidelines,
    register_guideline,
    resolve_guidelines,
    set_default_guidelines,
)
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


def test_guideline_defaults_preserve_priority_and_scope_filtering(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = tmp_path / "validation.md"
    second = tmp_path / "citation.md"
    first.write_text("Validation rules", encoding="utf-8")
    second.write_text("Citation rules", encoding="utf-8")
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    validation = register_guideline(workspace, str(first), scopes=["validation"])
    citation = register_guideline(workspace, str(second), scopes=["citation"])

    config = set_default_guidelines(workspace, [citation.record["id"], validation.record["id"]])
    resolved = resolve_guidelines(workspace, scope="validation")

    assert config["default_guideline_ids"] == ["guideline-002", "guideline-001"]
    assert read_yaml(workspace / "research-context.yaml")["guidelines"]["priority"] == [
        "guideline-002",
        "guideline-001",
    ]
    assert [item["id"] for item in resolved] == ["guideline-001"]
    assert resolved[0]["precedence"] == 2
    assert resolved[0]["selection_source"] == "default"


def test_explicit_guidelines_override_defaults(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = tmp_path / "default.md"
    second = tmp_path / "explicit.md"
    first.write_text("Default rules", encoding="utf-8")
    second.write_text("Explicit rules", encoding="utf-8")
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    default = register_guideline(workspace, str(first), scopes=["validation"])
    explicit = register_guideline(workspace, str(second), scopes=["validation"])
    set_default_guidelines(workspace, [default.record["id"]])

    resolved = resolve_guidelines(workspace, explicit_ids=[explicit.record["id"]], scope="validation")

    assert [item["id"] for item in resolved] == [explicit.record["id"]]
    assert resolved[0]["selection_source"] == "explicit"
