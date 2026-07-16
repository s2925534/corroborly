import zipfile
from pathlib import Path

import pytest

from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.citations import (
    apply_citation_plan,
    create_citation_plan,
    set_citation_plan_insertion_review_status,
)
from ledgerly.engine.conversion import extract_text
from ledgerly.engine.workspace import init_workspace


def test_create_citation_plan_writes_reviewable_plan_without_editing_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.md"
    original_text = "Container terminal automation uses berth planning evidence."
    target.write_text(original_text, encoding="utf-8")
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "provider": "local_folder",
                    "file_name": "paper.pdf",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                    "citation_metadata": {
                        "title": "Accepted Source",
                        "authors": ["Smith, A."],
                        "year": 2024,
                    },
                }
            ],
        },
    )

    result = create_citation_plan(workspace, str(target))

    assert result.yaml_path.is_file()
    assert result.markdown_path.is_file()
    assert target.read_text(encoding="utf-8") == original_text
    plan = read_yaml(result.yaml_path)
    assert plan["original_document_modified"] is False
    assert plan["insertions"][0]["source_id"] == "source-001"
    assert plan["insertions"][0]["suggested_inline_citation"] == "(Smith, 2024)"
    assert plan["insertions"][0]["review_status"] == "needs_human_review"


def test_create_citation_plan_rejects_unknown_citation_style(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.write_text("Some text.", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown citation style"):
        create_citation_plan(workspace, str(target), citation_style="harvard")


def test_create_citation_plan_mla_style(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    result = create_citation_plan(workspace, str(target), citation_style="mla")
    plan = read_yaml(result.yaml_path)
    assert plan["citation_style"] == "mla"
    # MLA in-text omits the year (this project doesn't track page numbers).
    assert plan["insertions"][0]["suggested_inline_citation"] == "(Smith)"
    reference = plan["references"]["accepted_workspace_evidence"][0]["reference"]
    assert reference.startswith('Smith, A.. "Accepted Source."')
    assert "2024" in reference


def test_create_citation_plan_chicago_style(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    result = create_citation_plan(workspace, str(target), citation_style="chicago")
    plan = read_yaml(result.yaml_path)
    assert plan["citation_style"] == "chicago"
    assert plan["insertions"][0]["suggested_inline_citation"] == "(Smith 2024)"
    reference = plan["references"]["accepted_workspace_evidence"][0]["reference"]
    assert reference.startswith('Smith, A.. 2024. "Accepted Source."')


def test_create_citation_plan_ieee_style_numbers_by_first_appearance(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    result = create_citation_plan(workspace, str(target), citation_style="ieee")
    plan = read_yaml(result.yaml_path)
    assert plan["citation_style"] == "ieee"
    assert plan["insertions"][0]["suggested_inline_citation"] == "[1]"
    reference = plan["references"]["accepted_workspace_evidence"][0]["reference"]
    assert reference.startswith("[1] Smith, A., ")


def test_create_citation_plan_default_apa_style_unchanged(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    result = create_citation_plan(workspace, str(target))
    plan = read_yaml(result.yaml_path)
    assert plan["citation_style"] == "apa7"
    assert plan["insertions"][0]["suggested_inline_citation"] == "(Smith, 2024)"


def test_apply_citation_plan_uses_the_requested_style_in_appended_references(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    plan = create_citation_plan(workspace, str(target), citation_style="ieee")
    insertion = plan.plan["insertions"][0]
    set_citation_plan_insertion_review_status(
        workspace, str(target), insertion["sentence_index"], insertion["source_id"], "accepted"
    )
    result = apply_citation_plan(workspace, str(target))
    revised_text = result.output_path.read_text(encoding="utf-8")
    assert "[1]" in revised_text
    assert "## References" in revised_text


def _citation_plan_fixture(tmp_path: Path):
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "provider": "local_folder",
                    "file_name": "paper.pdf",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                    "citation_metadata": {"title": "Accepted Source", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )
    return workspace, target


def test_set_citation_plan_insertion_review_status_updates_one_insertion(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    plan = create_citation_plan(workspace, str(target))
    insertion = plan.plan["insertions"][0]

    updated = set_citation_plan_insertion_review_status(
        workspace, str(target), insertion["sentence_index"], insertion["source_id"], "accepted"
    )

    assert updated["review_status"] == "accepted"
    persisted = read_yaml(plan.yaml_path)
    assert persisted["insertions"][0]["review_status"] == "accepted"

    result = apply_citation_plan(workspace, str(target))
    assert result.applied == 1


def test_set_citation_plan_insertion_review_status_rejects_invalid_status(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    plan = create_citation_plan(workspace, str(target))
    insertion = plan.plan["insertions"][0]

    with pytest.raises(ValueError, match="Invalid review_status"):
        set_citation_plan_insertion_review_status(
            workspace, str(target), insertion["sentence_index"], insertion["source_id"], "maybe-later"
        )


def test_set_citation_plan_insertion_review_status_rejects_unknown_insertion(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)
    create_citation_plan(workspace, str(target))

    with pytest.raises(ValueError, match="No insertion found"):
        set_citation_plan_insertion_review_status(workspace, str(target), 999, "source-999", "accepted")


def test_set_citation_plan_insertion_review_status_requires_plan_first(tmp_path: Path) -> None:
    workspace, target = _citation_plan_fixture(tmp_path)

    with pytest.raises(ValueError, match="does not exist"):
        set_citation_plan_insertion_review_status(workspace, str(target), 0, "source-001", "accepted")


def test_apply_citation_plan_creates_revised_copy_for_accepted_insertions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.md"
    original_text = "Container terminal automation uses berth planning evidence."
    target.write_text(original_text, encoding="utf-8")
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "provider": "local_folder",
                    "file_name": "paper.pdf",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                    "citation_metadata": {
                        "title": "Accepted Source",
                        "authors": ["Smith, A."],
                        "year": 2024,
                    },
                }
            ],
        },
    )
    plan = create_citation_plan(workspace, str(target))
    plan_data = read_yaml(plan.yaml_path)
    plan_data["insertions"][0]["review_status"] = "accepted"
    write_yaml(plan.yaml_path, plan_data)

    result = apply_citation_plan(workspace, str(target))

    revised = result.output_path.read_text(encoding="utf-8")
    assert target.read_text(encoding="utf-8") == original_text
    assert "evidence (Smith, 2024)." in revised
    assert "## References" in revised
    assert result.applied == 1
    report = read_yaml(result.report_path)
    assert report["original_document_modified"] is False
    assert report["document_version_id"] == result.version_id
    assert report["source_snapshot_version_id"] == result.source_snapshot_version_id

    versions = read_yaml(workspace / "document-vault.yaml")["versions"]
    applied_record = next(v for v in versions if v["version_id"] == result.version_id)
    assert applied_record["parent_version_id"] == result.source_snapshot_version_id
    assert applied_record["creation_reason"] == "citation_apply"
    assert applied_record["citation_plan_id"] == plan.yaml_path.stem
    assert applied_record["validation_report_id"] == Path(str(plan_data["validation_report"])).stem


def test_citation_plan_blocks_candidate_sources_by_default(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
    explicit_source = tmp_path / "candidate.txt"
    explicit_source.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")

    blocked = create_citation_plan(workspace, str(target), source_paths=[explicit_source])
    allowed = create_citation_plan(
        workspace,
        str(target),
        source_paths=[explicit_source],
        allow_candidate_citations=True,
    )

    assert blocked.plan["insertions"] == []
    assert blocked.plan["blocked_candidate_citations"][0]["source_status"] == "explicit"
    assert allowed.plan["insertions"][0]["source_id"] == "explicit-source-001"
    assert allowed.plan["allow_candidate_citations"] is True


def test_apply_citation_plan_creates_revised_docx_copy(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.docx"
    original_text = "Container terminal automation uses berth planning evidence."
    _write_docx(target, [original_text])
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "provider": "local_folder",
                    "file_name": "paper.pdf",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                    "citation_metadata": {
                        "title": "Accepted Source",
                        "authors": ["Smith, A."],
                        "year": 2024,
                    },
                }
            ],
        },
    )
    plan = create_citation_plan(workspace, str(target))
    plan_data = read_yaml(plan.yaml_path)
    plan_data["insertions"][0]["review_status"] = "accepted"
    write_yaml(plan.yaml_path, plan_data)

    result = apply_citation_plan(workspace, str(target))

    assert target.read_bytes() != result.output_path.read_bytes()
    assert result.output_path.suffix == ".docx"
    revised_text = extract_text(result.output_path)
    assert "evidence (Smith, 2024)." in revised_text
    assert "References" in revised_text
    report = read_yaml(result.report_path)
    assert report["target_format"] == "docx"
    assert report["output_format"] == "docx"


def test_apply_citation_plan_creates_markdown_derivative_for_pdf(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target = workspace / "artefacts" / "papers" / "draft.pdf"
    original_text = "Container terminal automation uses berth planning evidence."
    _write_minimal_pdf(target, original_text)
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "provider": "local_folder",
                    "file_name": "paper.pdf",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                    "citation_metadata": {
                        "title": "Accepted Source",
                        "authors": ["Smith, A."],
                        "year": 2024,
                    },
                }
            ],
        },
    )
    plan = create_citation_plan(workspace, str(target))
    plan_data = read_yaml(plan.yaml_path)
    plan_data["insertions"][0]["review_status"] = "accepted"
    write_yaml(plan.yaml_path, plan_data)

    result = apply_citation_plan(workspace, str(target))

    revised = result.output_path.read_text(encoding="utf-8")
    assert result.output_path.suffix == ".md"
    assert "evidence (Smith, 2024)." in revised
    report = read_yaml(result.report_path)
    assert report["target_format"] == "pdf"
    assert report["output_format"] == "md"


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{namespace}">
  <w:body>{body}</w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr("word/document.xml", document_xml)


def _write_minimal_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    path.write_bytes(f"%PDF-1.4\nstream\nBT\n({escaped}) Tj\nET\nendstream\n%%EOF\n".encode("latin-1"))
