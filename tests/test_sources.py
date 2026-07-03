from pathlib import Path

import pytest

from researchboss.core.yamlio import read_yaml
from researchboss.engine.sources import (
    iter_source_files,
    list_sources,
    scan_sources,
    set_source_status,
    source_counts,
)
from researchboss.engine.workspace import init_workspace


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="M.Phil",
        topic="",
    )
    return workspace


def test_iter_source_files_filters_supported_extensions(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    supported = source_root / "paper.PDF"
    unsupported = source_root / "image.png"
    nested = source_root / "nested"
    nested.mkdir()
    note = nested / "note.md"

    supported.write_text("pdf-ish", encoding="utf-8")
    unsupported.write_text("image-ish", encoding="utf-8")
    note.write_text("# Note", encoding="utf-8")

    assert sorted(p.name for p in iter_source_files(source_root)) == ["note.md", "paper.PDF"]


def test_scan_sources_registers_new_files_and_skips_duplicates(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    first = source_root / "paper.txt"
    duplicate = source_root / "copy.md"
    first.write_text("same content", encoding="utf-8")
    duplicate.write_text("same content", encoding="utf-8")

    result = scan_sources(workspace, source_root)

    assert result.processed == 2
    assert result.added == 1
    assert result.duplicates == 1
    assert result.skipped == 0

    register = read_yaml(workspace / "source-register.yaml")
    assert len(register["sources"]) == 1
    source = register["sources"][0]
    assert source["status"] == "pending_review"
    assert source["source_id"].endswith(source["content_hash"][:10])

    second_result = scan_sources(workspace, source_root)
    assert second_result.added == 0
    assert second_result.duplicates == 2


def test_scan_sources_can_start_new_files_as_maybe(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("content", encoding="utf-8")

    result = scan_sources(workspace, source_root, initial_status="maybe")

    assert result.added == 1
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["status"] == "maybe"
    assert read_yaml(workspace / "maybe-sources.yaml")["source_ids"] == [source["source_id"]]


def test_scan_sources_rejects_invalid_initial_status(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()

    with pytest.raises(ValueError, match="Invalid initial source status"):
        scan_sources(workspace, source_root, initial_status="accepted")


def test_set_source_status_updates_register_and_review_lists(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    scan_sources(workspace, source_root)

    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]

    set_source_status(workspace, source_id=source_id, new_status="accepted")
    assert source_counts(workspace)["accepted"] == 1
    assert read_yaml(workspace / "accepted-sources.yaml")["source_ids"] == [source_id]

    set_source_status(workspace, source_id=source_id, new_status="maybe")
    assert read_yaml(workspace / "accepted-sources.yaml")["source_ids"] == []
    assert read_yaml(workspace / "maybe-sources.yaml")["source_ids"] == [source_id]

    set_source_status(workspace, source_id=source_id, new_status="ignored", ignore_reason="Out of scope")
    assert read_yaml(workspace / "maybe-sources.yaml")["source_ids"] == []
    assert read_yaml(workspace / "ignored-sources.yaml")["ignored"] == [
        {"source_id": source_id, "reason": "Out of scope"}
    ]


def test_set_source_status_rejects_unknown_source_id(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    with pytest.raises(ValueError, match="Unknown source_id"):
        set_source_status(workspace, source_id="missing", new_status="accepted")


def test_list_sources_rejects_invalid_status_filter(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    with pytest.raises(ValueError, match="Invalid source status"):
        list_sources(workspace, status="done")


def test_set_source_status_rejects_invalid_review_status(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("content", encoding="utf-8")
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]

    with pytest.raises(ValueError, match="Invalid review status"):
        set_source_status(workspace, source_id=source_id, new_status="done")
