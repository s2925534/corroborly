from pathlib import Path

import pytest

from researchboss.core.yamlio import write_yaml
from researchboss.engine.artefacts import register_artefact
from researchboss.engine.document_targets import resolve_document_target
from researchboss.engine.workspace import init_workspace


def test_resolve_document_target_from_existing_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target_path = cwd / "draft.md"
    target_path.write_text("# Draft", encoding="utf-8")

    target = resolve_document_target(workspace, "draft.md", cwd=cwd)

    assert target.kind == "file_path"
    assert target.source == "path"
    assert target.path == target_path.resolve()


def test_resolve_document_target_from_artefact_id_and_relative_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.write_text("# Summary", encoding="utf-8")
    write_yaml(
        workspace / "artefact-registry.yaml",
        {
            "version": 1,
            "artefacts": [
                {
                    "id": "artefact-001",
                    "title": "Source Summary",
                    "type": "source-summary-report",
                    "path": "artefacts/reports/summary.md",
                }
            ],
        },
    )

    target = resolve_document_target(workspace, "artefact-001")

    assert target.kind == "artefact"
    assert target.source == "artefact_id"
    assert target.artefact_id == "artefact-001"
    assert target.artefact_title == "Source Summary"
    assert target.artefact_type == "source-summary-report"
    assert target.path == artefact_path.resolve()


def test_resolve_document_target_from_artefact_title(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    artefact_path = workspace / "artefacts" / "papers" / "paper.md"
    artefact_path.write_text("# Paper", encoding="utf-8")
    register_artefact(workspace, title="Main Paper Draft", artefact_type="paper", path=artefact_path)

    target = resolve_document_target(workspace, "main paper draft")

    assert target.source == "artefact_title"
    assert target.artefact_title == "Main Paper Draft"
    assert target.path == artefact_path.resolve()


def test_resolve_document_target_from_primary_output_alias_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    thesis_path = workspace / "artefacts" / "thesis" / "chapter-1.docx"
    thesis_path.write_text("placeholder", encoding="utf-8")

    target = resolve_document_target(workspace, "thesis")

    assert target.kind == "primary_output_alias"
    assert target.source == "primary_output_alias"
    assert target.path == thesis_path.resolve()


def test_resolve_document_target_from_supported_artefact_type_with_spaces(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    report_path = workspace / "artefacts" / "reports" / "source-summary-report.md"
    report_path.write_text("# Summary", encoding="utf-8")

    target = resolve_document_target(workspace, "source summary report")

    assert target.kind == "artefact_type"
    assert target.source == "supported_artefact_type"
    assert target.artefact_type == "source-summary-report"
    assert target.path == report_path.resolve()


def test_resolve_document_target_rejects_ambiguous_titles(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    first = workspace / "artefacts" / "reports" / "first.md"
    second = workspace / "artefacts" / "reports" / "second.md"
    first.write_text("# First", encoding="utf-8")
    second.write_text("# Second", encoding="utf-8")
    register_artefact(workspace, title="Summary", artefact_type="report", path=first)
    register_artefact(workspace, title="summary", artefact_type="report", path=second)

    with pytest.raises(ValueError, match="title is ambiguous"):
        resolve_document_target(workspace, "SUMMARY")


def test_resolve_document_target_rejects_ambiguous_alias_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    (workspace / "artefacts" / "notes" / "one.md").write_text("One", encoding="utf-8")
    (workspace / "artefacts" / "notes" / "two.txt").write_text("Two", encoding="utf-8")

    with pytest.raises(ValueError, match="alias is ambiguous"):
        resolve_document_target(workspace, "notes")


def test_resolve_document_target_rejects_unknown_targets(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    with pytest.raises(ValueError, match="Could not resolve document target"):
        resolve_document_target(workspace, "missing-document")
