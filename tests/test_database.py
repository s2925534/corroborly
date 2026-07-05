from __future__ import annotations

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from researchboss.cli import app
from researchboss.core.yamlio import read_yaml
from researchboss.engine.database import (
    apply_pending_changes,
    database_path,
    database_privacy_report,
    database_status,
    init_database,
    pending_changes_report,
    rebuild_database,
    sync_database,
)
from researchboss.engine.workspace import init_workspace


runner = CliRunner()


def test_database_init_sync_status_and_rebuild(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    init_result = init_database(workspace)
    sync_result = sync_database(workspace)
    status_result = database_status(workspace)
    rebuild_result = rebuild_database(workspace)

    assert init_result.path == workspace / "researchboss.sqlite"
    assert init_result.path.is_file()
    assert sync_result.report["files_synced"] >= 10
    assert sync_result.report["source_of_truth"] == "workspace_yaml_markdown"
    assert status_result.report["status"] == "ok"
    assert status_result.report["integrity_check"] == "ok"
    assert rebuild_result.report["status"] == "rebuilt"


def test_database_sync_tracks_file_revisions_and_conflicts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    sync_database(workspace)
    context = read_yaml(workspace / "research-context.yaml")
    context["project"]["topic"] = "Updated topic"
    from researchboss.core.yamlio import write_yaml

    write_yaml(workspace / "research-context.yaml", context)

    sync_result = sync_database(workspace)

    assert sync_result.report["files_changed"] == 1
    with sqlite3.connect(database_path(workspace)) as conn:
        row = conn.execute(
            "select file_revision, conflict_status from sync_files where relative_path = 'research-context.yaml'"
        ).fetchone()
    assert row[0] == 2
    assert row[1] == "clean"


def test_database_has_memory_alias_and_fts_entries(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    text_path = workspace / "sources_text" / "source-001.txt"
    text_path.write_text("container terminal automation evidence", encoding="utf-8")

    sync_database(workspace)

    with sqlite3.connect(database_path(workspace)) as conn:
        memory_count = conn.execute("select count(*) from memory_entries").fetchone()[0]
        thesis_alias = conn.execute("select target_value from document_aliases where alias = 'thesis'").fetchone()
        fts_hit = conn.execute(
            "select count(*) from fts_index_search where fts_index_search match 'container'"
        ).fetchone()[0]
    assert memory_count >= 5
    assert thesis_alias[0] == "artefacts/thesis"
    assert fts_hit >= 1


def test_database_indexes_validation_citation_and_guidelines(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    guideline_registry = workspace / "guidelines" / "guidelines.yaml"
    guideline_registry.parent.mkdir(parents=True, exist_ok=True)
    from researchboss.core.yamlio import write_yaml

    write_yaml(
        guideline_registry,
        {
            "version": 1,
            "guidelines": [
                {
                    "id": "guideline-001",
                    "title": "Faculty Rules",
                    "scopes": ["validation"],
                    "snapshot_path": "guidelines/snapshots/faculty.md",
                    "text_path": "guidelines/text/faculty.txt",
                }
            ],
        },
    )
    write_yaml(
        workspace / "outputs" / "validation" / "document-validation-draft.yaml",
        {
            "version": 1,
            "target": {"path": "artefacts/papers/draft.md"},
            "summary": {"source_count": 1},
            "unsupported_claims": [{"text": "Unsupported"}],
            "weakly_supported_claims": [],
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "overlap_score": 0.75,
                    "matched_terms": ["container", "automation"],
                }
            ],
        },
    )
    write_yaml(
        workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml",
        {
            "version": 1,
            "target": {"path": "artefacts/papers/draft.md"},
            "plan_status": "review_required",
            "insertions": [{"source_id": "source-001"}],
        },
    )

    sync_database(workspace)
    status = database_status(workspace)

    with sqlite3.connect(database_path(workspace)) as conn:
        guideline_count = conn.execute("select count(*) from guideline_registrations").fetchone()[0]
        validation_count = conn.execute("select count(*) from validation_runs").fetchone()[0]
        evidence_count = conn.execute("select count(*) from evidence_matches").fetchone()[0]
        citation_count = conn.execute("select count(*) from citation_plans").fetchone()[0]
        document_version_count = conn.execute("select count(*) from document_versions").fetchone()[0]

    assert guideline_count == 1
    assert validation_count == 1
    assert evidence_count == 1
    assert citation_count == 1
    assert document_version_count == 0
    assert status.report["counts"]["guideline_registrations"] == 1
    assert status.report["counts"]["validation_runs"] == 1
    assert status.report["counts"]["evidence_matches"] == 1
    assert status.report["counts"]["citation_plans"] == 1
    assert status.report["counts"]["document_versions"] == 0


def test_database_pending_changes_are_reviewed_before_apply(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    init_database(workspace)

    with sqlite3.connect(database_path(workspace)) as conn:
        conn.execute(
            """
            insert into pending_changes (relative_path, proposed_content, reason, created_at)
            values ('memory.md', '# Memory\n\nReviewed note.\n', 'test change', '2026-01-01T00:00:00+00:00')
            """
        )

    review = pending_changes_report(workspace)
    dry_run = apply_pending_changes(workspace, apply=False)
    applied = apply_pending_changes(workspace, apply=True)

    assert review.report["pending_count"] == 1
    assert dry_run.report["review_count"] == 1
    assert applied.report["applied_count"] == 1
    assert (workspace / "memory.md").read_text(encoding="utf-8") == "# Memory\n\nReviewed note.\n"


def test_database_privacy_report_passes_for_default_sync(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    sync_database(workspace)

    report = database_privacy_report(workspace)

    assert report.report["status"] == "ok"
    assert report.report["stores_original_documents"] is False
    assert report.report["stores_api_keys_intentionally"] is False


def test_cli_db_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    for args in [
        ["db", "init", "--workspace", str(workspace), "--quiet"],
        ["db", "sync", "--workspace", str(workspace), "--quiet"],
        ["db", "status", "--workspace", str(workspace), "--quiet"],
        ["db", "apply-pending", "--review", "--workspace", str(workspace), "--quiet"],
        ["db", "privacy", "--workspace", str(workspace), "--quiet"],
        ["db", "rebuild", "--workspace", str(workspace), "--quiet"],
    ]:
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
