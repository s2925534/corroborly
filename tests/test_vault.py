from pathlib import Path

import pytest

from researchboss.core.constants import WORKSPACE_DIRS
from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.backup import create_workspace_backup, inspect_backup
from researchboss.engine.vault import (
    compare_document_versions,
    create_document_version,
    diff_document_versions,
    ensure_vault_dirs,
    intake_uploaded_artefact,
    intake_uploaded_artefact_batch,
    list_document_versions,
    list_uploaded_artefacts,
    resolve_uploaded_artefact_file,
    restore_document_version,
    vault_layout,
)
from researchboss.engine.workspace import init_workspace


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    return workspace


def test_vault_dirs_are_created_at_init(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    for rel_path in WORKSPACE_DIRS:
        if rel_path.startswith("document_vault"):
            assert (workspace / rel_path).is_dir(), rel_path


def test_ensure_vault_dirs_matches_layout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    layout = ensure_vault_dirs(workspace)
    assert set(layout.keys()) == {
        "originals",
        "versions",
        "derived_text",
        "diffs",
        "manifests",
        "ai_edit_sessions",
        "upload_originals",
        "upload_renamed",
    }
    for path in layout.values():
        assert path.is_dir()
        assert path.is_relative_to(workspace)


def test_create_document_version_snapshots_first_version_and_original(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("Draft v1\n", encoding="utf-8")

    record = create_document_version(workspace, str(target_path))

    assert record["version_id"] == "docv-001"
    assert record["parent_version_id"] is None
    assert record["creation_reason"] == "manual_snapshot"
    assert record["original_file_modified"] is False
    layout = vault_layout(workspace)
    stored_path = Path(record["stored_path"])
    assert stored_path.is_file()
    assert stored_path.read_text(encoding="utf-8") == "Draft v1\n"
    original_copy = layout["originals"] / f"{record['version_id']}.md"
    assert original_copy.is_file()
    manifest_path = layout["manifests"] / f"{record['version_id']}.yaml"
    assert manifest_path.is_file()
    assert target_path.read_text(encoding="utf-8") == "Draft v1\n"  # original untouched


def test_create_document_version_links_parent_and_skips_unchanged(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("Draft v1\n", encoding="utf-8")

    first = create_document_version(workspace, str(target_path))
    unchanged = create_document_version(workspace, str(target_path))
    assert unchanged["version_id"] == first["version_id"]

    target_path.write_text("Draft v2\n", encoding="utf-8")
    second = create_document_version(workspace, str(target_path))

    assert second["version_id"] == "docv-002"
    assert second["parent_version_id"] == first["version_id"]
    versions = list_document_versions(workspace, str(target_path))
    assert [v["version_id"] for v in versions] == ["docv-001", "docv-002"]


def test_create_document_version_rejects_missing_target(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError):
        create_document_version(workspace, str(workspace / "does-not-exist.md"))


def test_diff_document_versions_reports_line_changes(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("line one\nline two\n", encoding="utf-8")
    first = create_document_version(workspace, str(target_path))
    target_path.write_text("line one\nline three\n", encoding="utf-8")
    second = create_document_version(workspace, str(target_path))

    report = diff_document_versions(workspace, first["version_id"], second["version_id"])

    assert report["diff_supported"] is True
    assert report["changed"] is True
    assert any("line three" in line for line in report["lines"])
    assert Path(report["diff_path"]).is_file()


def test_diff_document_versions_flags_unsupported_binary_formats(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.docx"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(b"not-really-docx-bytes")
    first = create_document_version(workspace, str(target_path))
    target_path.write_bytes(b"different-bytes")
    second = create_document_version(workspace, str(target_path))

    report = diff_document_versions(workspace, first["version_id"], second["version_id"])

    assert report["diff_supported"] is False
    assert report["lines"] == []


def test_restore_document_version_creates_new_copy_without_overwrite(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("original text\n", encoding="utf-8")
    first = create_document_version(workspace, str(target_path))
    target_path.write_text("edited text\n", encoding="utf-8")
    create_document_version(workspace, str(target_path))

    restored = restore_document_version(workspace, first["version_id"])

    restored_path = Path(restored["restored_to_path"])
    assert restored_path.is_file()
    assert restored_path.read_text(encoding="utf-8") == "original text\n"
    assert restored["restored_from_version_id"] == first["version_id"]
    assert target_path.read_text(encoding="utf-8") == "edited text\n"  # current document untouched
    assert restored["parent_version_id"] == first["version_id"]


def test_restore_document_version_does_not_overwrite_existing_destination(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("original text\n", encoding="utf-8")
    first = create_document_version(workspace, str(target_path))

    conflicting_output = workspace / "artefacts" / "notes" / "already-here.md"
    conflicting_output.write_text("existing\n", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        restore_document_version(workspace, first["version_id"], output_path=conflicting_output)


def test_backup_includes_document_vault_without_zotero_originals(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("original text\n", encoding="utf-8")
    create_document_version(workspace, str(target_path))

    backup_path = create_workspace_backup(workspace)
    inspection = inspect_backup(backup_path)

    assert any(name.startswith("document_vault/versions/") for name in inspection["files"])
    assert any(name.startswith("document_vault/manifests/") for name in inspection["files"])
    assert "document-vault.yaml" in inspection["files"]
    assert inspection["contains_original_sources"] is False


def test_compare_document_versions_reports_not_comparable_without_validation_links(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("v1\n", encoding="utf-8")
    first = create_document_version(workspace, str(target_path))
    target_path.write_text("v2\n", encoding="utf-8")
    second = create_document_version(workspace, str(target_path))

    comparison = compare_document_versions(workspace, first["version_id"], second["version_id"])

    assert comparison["comparable"] is False
    assert "validation report" in comparison["reason"]
    assert Path(comparison["comparison_path"]).is_file()


def test_compare_document_versions_diffs_strengths_weaknesses_claims_and_references(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("v1\n", encoding="utf-8")

    write_yaml(
        workspace / "outputs" / "validation" / "document-validation-draft-a.yaml",
        {
            "strengths": [{"kind": "source_overlap", "message": "ok"}],
            "weaknesses": [{"kind": "unsupported_sentence_terms", "message": "bad"}],
            "unsupported_claims": [{"text": "Claim one is unsupported."}],
            "weakly_supported_claims": [],
            "references": {"accepted_workspace_evidence": [{"reference": "Smith (2024)."}]},
        },
    )
    first = create_document_version(
        workspace, str(target_path), validation_report_id="document-validation-draft-a"
    )

    target_path.write_text("v2\n", encoding="utf-8")
    write_yaml(
        workspace / "outputs" / "validation" / "document-validation-draft-b.yaml",
        {
            "strengths": [],
            "weaknesses": [{"kind": "unsupported_sentence_terms", "message": "bad"}, {"kind": "weak_sentence_terms", "message": "weak"}],
            "unsupported_claims": [],
            "weakly_supported_claims": [{"text": "Claim two is weak."}],
            "references": {
                "accepted_workspace_evidence": [
                    {"reference": "Smith (2024)."},
                    {"reference": "Doe (2023)."},
                ]
            },
        },
    )
    second = create_document_version(
        workspace, str(target_path), validation_report_id="document-validation-draft-b"
    )

    comparison = compare_document_versions(workspace, first["version_id"], second["version_id"])

    assert comparison["comparable"] is True
    assert comparison["strengths"] == {"added": [], "removed": ["source_overlap"]}
    assert comparison["weaknesses"] == {"added": ["weak_sentence_terms"], "removed": []}
    assert comparison["unsupported_claims"] == {"added": [], "removed": ["Claim one is unsupported."]}
    assert comparison["weakly_supported_claims"] == {"added": ["Claim two is weak."], "removed": []}
    assert comparison["references"] == {"added": ["Doe (2023)."], "removed": []}


def test_intake_uploaded_artefact_copies_without_modifying_the_upload(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "incoming" / "Draft Chapter.docx"
    upload_source.parent.mkdir(parents=True, exist_ok=True)
    original_bytes = b"fake docx bytes"
    upload_source.write_bytes(original_bytes)

    record = intake_uploaded_artefact(
        workspace, upload_source, title="Draft Chapter One", author="Smith, A.", year="2024"
    )

    assert record["upload_id"] == "upload-001"
    assert record["original_file_modified"] is False
    assert upload_source.read_bytes() == original_bytes  # upload itself untouched

    renamed_path = Path(record["vault_renamed_path"])
    assert renamed_path.is_file()
    assert renamed_path.read_bytes() == original_bytes
    assert renamed_path.name.startswith("smith_2024_draft-chapter-one_upload-001")

    original_copy_path = Path(record["vault_original_copy_path"])
    assert original_copy_path.is_file()
    assert original_copy_path.name == "Draft Chapter.docx"
    assert original_copy_path.read_bytes() == original_bytes

    assert list_uploaded_artefacts(workspace) == [record]


def test_intake_uploaded_artefact_handles_original_filename_collisions(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first_source = tmp_path / "batch1" / "draft.pdf"
    second_source = tmp_path / "batch2" / "draft.pdf"
    first_source.parent.mkdir(parents=True, exist_ok=True)
    second_source.parent.mkdir(parents=True, exist_ok=True)
    first_source.write_bytes(b"first upload")
    second_source.write_bytes(b"second upload")

    first_record = intake_uploaded_artefact(workspace, first_source)
    second_record = intake_uploaded_artefact(workspace, second_source)

    first_copy = Path(first_record["vault_original_copy_path"])
    second_copy = Path(second_record["vault_original_copy_path"])
    assert first_copy != second_copy
    assert first_copy.read_bytes() == b"first upload"
    assert second_copy.read_bytes() == b"second upload"
    # renamed copies never collide either, since the upload ID is embedded in the name
    assert first_record["vault_renamed_path"] != second_record["vault_renamed_path"]
    assert first_record["renamed_file_name"] != second_record["renamed_file_name"]


def test_intake_uploaded_artefact_uses_filename_stem_when_no_title_given(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "methodology-notes.md"
    upload_source.write_text("# Notes", encoding="utf-8")

    record = intake_uploaded_artefact(workspace, upload_source)

    assert record["title"] == "methodology-notes"
    assert record["author_token"] == "unknown-author"
    assert record["year"] == "nd"
    assert "methodology-notes" in record["renamed_file_name"]


def test_intake_uploaded_artefact_rejects_missing_source(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    with pytest.raises(ValueError):
        intake_uploaded_artefact(workspace, tmp_path / "does-not-exist.pdf")


def test_resolve_uploaded_artefact_file_returns_renamed_vault_copy(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("# Preview Me", encoding="utf-8")
    record = intake_uploaded_artefact(workspace, upload_source)

    resolved = resolve_uploaded_artefact_file(workspace, record["upload_id"])

    assert resolved == Path(record["vault_renamed_path"]).resolve()
    assert resolved.read_text(encoding="utf-8") == "# Preview Me"


def test_resolve_uploaded_artefact_file_rejects_unknown_upload_id(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    with pytest.raises(ValueError, match="Unknown upload_id"):
        resolve_uploaded_artefact_file(workspace, "bogus-id")


def test_resolve_uploaded_artefact_file_rejects_path_outside_vault(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    upload_source = tmp_path / "notes.md"
    upload_source.write_text("# Notes", encoding="utf-8")
    record = intake_uploaded_artefact(workspace, upload_source)

    ledger_path = workspace / "document-vault.yaml"
    ledger = read_yaml(ledger_path)
    outside_path = tmp_path / "escaped.md"
    outside_path.write_text("# Escaped", encoding="utf-8")
    ledger["uploads"][0]["vault_renamed_path"] = str(outside_path)
    write_yaml(ledger_path, ledger)

    with pytest.raises(ValueError, match="outside the vault"):
        resolve_uploaded_artefact_file(workspace, record["upload_id"])


def test_intake_batch_rejects_whole_batch_when_over_max_files(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    paths = []
    for i in range(3):
        path = incoming / f"file-{i}.md"
        path.write_text(f"content {i}", encoding="utf-8")
        paths.append(path)

    with pytest.raises(ValueError, match="exceeds the configured limit"):
        intake_uploaded_artefact_batch(workspace, paths, max_files=2)

    assert list_uploaded_artefacts(workspace) == []  # nothing copied


def test_intake_batch_classifies_accepted_duplicate_rejected_and_failed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    incoming = tmp_path / "incoming"
    incoming.mkdir()

    good_file = incoming / "good.md"
    good_file.write_text("unique content", encoding="utf-8")
    duplicate_file = incoming / "duplicate.md"
    duplicate_file.write_text("unique content", encoding="utf-8")  # same bytes as good_file
    wrong_extension = incoming / "notes.exe"
    wrong_extension.write_text("binary-ish", encoding="utf-8")
    too_large = incoming / "big.md"
    too_large.write_text("x" * 100, encoding="utf-8")
    missing_file = incoming / "missing.md"

    report = intake_uploaded_artefact_batch(
        workspace,
        [good_file, duplicate_file, wrong_extension, too_large, missing_file],
        max_file_size_bytes=50,
        allowed_extensions={".md"},
    )

    assert report["processed"] == 5
    assert report["accepted"] == 1
    assert report["duplicate"] == 1
    assert report["rejected"] == 2
    assert report["failed"] == 1
    statuses = {row["file_name"]: row["status"] for row in report["rows"]}
    assert statuses["good.md"] == "accepted"
    assert statuses["duplicate.md"] == "duplicate"
    assert statuses["notes.exe"] == "rejected"
    assert statuses["big.md"] == "rejected"
    assert statuses["missing.md"] == "failed"
    assert len(list_uploaded_artefacts(workspace)) == 1


def test_intake_batch_writes_report_to_outputs_validation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    path = incoming / "notes.md"
    path.write_text("content", encoding="utf-8")

    intake_uploaded_artefact_batch(workspace, [path])

    report_path = workspace / "outputs" / "validation" / "upload-batch-report.yaml"
    assert report_path.is_file()
