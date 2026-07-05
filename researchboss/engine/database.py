from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchboss.core.constants import WORKSPACE_FILES
from researchboss.core.yamlio import read_yaml
from researchboss.engine.document_targets import PRIMARY_OUTPUT_ALIASES
from researchboss.engine.artefacts import list_artefacts


DB_FILE_NAME = "researchboss.sqlite"
SCHEMA_VERSION = 1
SENSITIVE_PATTERNS = ("api_key", "apikey", "secret", "token", "password", "openai_api_key", "anthropic_api_key")


@dataclass(frozen=True)
class DbCommandResult:
    path: Path
    report: dict[str, Any]


def database_path(workspace: Path) -> Path:
    return workspace / DB_FILE_NAME


def init_database(workspace: Path) -> DbCommandResult:
    path = database_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        _create_schema(conn)
        _set_meta(conn, "schema_version", str(SCHEMA_VERSION))
        _set_meta(conn, "source_of_truth", "workspace_yaml_markdown")
        _set_meta(conn, "sync_policy", "sqlite_index_cache_reviewed_pending_changes_only")
    return DbCommandResult(path, {"status": "initialized", "database": str(path), "schema_version": SCHEMA_VERSION})


def rebuild_database(workspace: Path) -> DbCommandResult:
    path = database_path(workspace)
    if path.exists():
        path.unlink()
    init_database(workspace)
    result = sync_database(workspace)
    result.report["status"] = "rebuilt"
    return result


def sync_database(workspace: Path) -> DbCommandResult:
    path = database_path(workspace)
    init_database(workspace)
    now = _utc_now()
    sync_files = workspace_sync_files(workspace)
    synced = 0
    changed = 0
    missing = 0
    conflicts = 0

    with _connect(path) as conn:
        _create_schema(conn)
        for relative_path in sync_files:
            file_path = workspace / relative_path
            previous = conn.execute(
                "select sha256, db_revision, file_revision from sync_files where relative_path = ?",
                (relative_path,),
            ).fetchone()
            if not file_path.exists():
                missing += 1
                conn.execute(
                    """
                    insert into sync_files (
                        relative_path, sha256, size_bytes, mtime, last_synced_at, db_revision,
                        file_revision, dirty_flag, conflict_status, file_kind
                    )
                    values (?, '', 0, 0, ?, 1, 0, 1, 'missing', ?)
                    on conflict(relative_path) do update set
                        dirty_flag = 1,
                        conflict_status = 'missing',
                        last_synced_at = excluded.last_synced_at
                    """,
                    (relative_path, now, _file_kind(relative_path)),
                )
                continue

            digest = _sha256(file_path)
            stat = file_path.stat()
            db_revision = int(previous["db_revision"]) if previous else 0
            file_revision = int(previous["file_revision"]) if previous else 0
            dirty_flag = 0
            conflict_status = "clean"
            if previous and previous["sha256"] != digest:
                changed += 1
                file_revision += 1
            if _has_pending_change(conn, relative_path):
                dirty_flag = 1
                conflict_status = "pending_sqlite_change"
                conflicts += 1
            conn.execute(
                """
                insert into sync_files (
                    relative_path, sha256, size_bytes, mtime, last_synced_at, db_revision,
                    file_revision, dirty_flag, conflict_status, file_kind
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(relative_path) do update set
                    sha256 = excluded.sha256,
                    size_bytes = excluded.size_bytes,
                    mtime = excluded.mtime,
                    last_synced_at = excluded.last_synced_at,
                    file_revision = excluded.file_revision,
                    dirty_flag = excluded.dirty_flag,
                    conflict_status = excluded.conflict_status,
                    file_kind = excluded.file_kind
                """,
                (
                    relative_path,
                    digest,
                    stat.st_size,
                    stat.st_mtime,
                    now,
                    max(db_revision, 1),
                    max(file_revision, 1),
                    dirty_flag,
                    conflict_status,
                    _file_kind(relative_path),
                ),
            )
            synced += 1

        _sync_memory_defaults(conn, now)
        _sync_document_aliases(conn, workspace, now)
        _sync_fts_indexes(conn, workspace, now)
        _set_meta(conn, "last_sync_at", now)

    return DbCommandResult(
        path,
        {
            "status": "synced",
            "database": str(path),
            "files_synced": synced,
            "files_changed": changed,
            "files_missing": missing,
            "conflicts": conflicts,
            "source_of_truth": "workspace_yaml_markdown",
            "write_back_policy": "pending_changes_require_review_and_apply",
        },
    )


def database_status(workspace: Path) -> DbCommandResult:
    path = database_path(workspace)
    if not path.exists():
        return DbCommandResult(path, {"status": "missing", "database": str(path), "repair": "run researchboss db init"})
    with _connect(path) as conn:
        _create_schema(conn)
        integrity = conn.execute("pragma integrity_check").fetchone()[0]
        sync_counts = {
            row["conflict_status"]: row["count"]
            for row in conn.execute("select conflict_status, count(*) as count from sync_files group by conflict_status")
        }
        counts = {
            "sync_files": _count(conn, "sync_files"),
            "pending_changes": _count(conn, "pending_changes", "status = 'pending'"),
            "memory_entries": _count(conn, "memory_entries"),
            "document_aliases": _count(conn, "document_aliases"),
            "fts_entries": _count(conn, "fts_index"),
        }
        report = {
            "status": "ok" if integrity == "ok" else "needs_repair",
            "database": str(path),
            "schema_version": _get_meta(conn, "schema_version"),
            "source_of_truth": _get_meta(conn, "source_of_truth"),
            "last_sync_at": _get_meta(conn, "last_sync_at"),
            "integrity_check": integrity,
            "counts": counts,
            "sync_conflicts": sync_counts,
            "repair": "run researchboss db rebuild" if integrity != "ok" else None,
        }
    return DbCommandResult(path, report)


def pending_changes_report(workspace: Path) -> DbCommandResult:
    path = database_path(workspace)
    init_database(workspace)
    with _connect(path) as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                select id, relative_path, reason, created_at, status
                from pending_changes
                where status = 'pending'
                order by id
                """
            )
        ]
    return DbCommandResult(path, {"status": "review", "pending_count": len(rows), "pending_changes": rows})


def apply_pending_changes(workspace: Path, *, apply: bool = False) -> DbCommandResult:
    path = database_path(workspace)
    init_database(workspace)
    now = _utc_now()
    applied = []
    reviewed = []
    with _connect(path) as conn:
        rows = list(
            conn.execute(
                "select id, relative_path, proposed_content from pending_changes where status = 'pending' order by id"
            )
        )
        if not apply:
            reviewed = [dict(row) | {"proposed_content": None} for row in rows]
        else:
            for row in rows:
                relative_path = str(row["relative_path"])
                if relative_path not in workspace_sync_files(workspace):
                    conn.execute(
                        "update pending_changes set status = 'blocked', applied_at = ?, reason = reason || '; blocked path' where id = ?",
                        (now, row["id"]),
                    )
                    continue
                target = workspace / relative_path
                target.write_text(str(row["proposed_content"]), encoding="utf-8")
                conn.execute(
                    "update pending_changes set status = 'applied', applied_at = ? where id = ?",
                    (now, row["id"]),
                )
                applied.append(relative_path)
    if apply:
        sync_database(workspace)
    return DbCommandResult(
        path,
        {
            "status": "applied" if apply else "review",
            "applied_count": len(applied),
            "review_count": len(reviewed),
            "applied": applied,
            "review": reviewed,
            "write_back_policy": "explicit_apply_only",
        },
    )


def database_privacy_report(workspace: Path) -> DbCommandResult:
    path = database_path(workspace)
    if not path.exists():
        return DbCommandResult(path, {"status": "missing", "issues": ["database_missing"]})
    issues: list[dict[str, Any]] = []
    with _connect(path) as conn:
        for table, columns in _text_columns(conn).items():
            for column in columns:
                rows = conn.execute(f"select rowid, {column} as value from {table}").fetchall()
                for row in rows:
                    value = str(row["value"] or "")
                    lower = value.lower()
                    matched = [pattern for pattern in SENSITIVE_PATTERNS if pattern in lower]
                    if matched:
                        issues.append(
                            {
                                "table": table,
                                "column": column,
                                "rowid": row["rowid"],
                                "issue": "sensitive_key_pattern",
                                "patterns": matched,
                            }
                        )
        oversized = [
            dict(row)
            for row in conn.execute(
                """
                select relative_path, size_bytes
                from sync_files
                where relative_path like 'sources_original/%' or size_bytes > 1000000
                """
            )
        ]
        for row in oversized:
            issues.append(
                {
                    "table": "sync_files",
                    "column": "relative_path",
                    "issue": "original_or_large_file_should_not_be_mirrored_as_content",
                    "relative_path": row["relative_path"],
                    "size_bytes": row["size_bytes"],
                }
            )
    return DbCommandResult(
        path,
        {
            "status": "ok" if not issues else "needs_review",
            "issue_count": len(issues),
            "issues": issues,
            "stores_original_documents": False,
            "stores_api_keys_intentionally": False,
            "zotero_write_boundary": "no Zotero-owned files are written by database commands",
        },
    )


def workspace_sync_files(workspace: Path) -> list[str]:
    names = [
        WORKSPACE_FILES.research_context,
        WORKSPACE_FILES.research_state,
        WORKSPACE_FILES.research_stages,
        WORKSPACE_FILES.research_questions,
        WORKSPACE_FILES.research_question_candidates,
        WORKSPACE_FILES.rejected_research_questions,
        WORKSPACE_FILES.source_register,
        WORKSPACE_FILES.accepted_sources,
        WORKSPACE_FILES.ignored_sources,
        WORKSPACE_FILES.maybe_sources,
        WORKSPACE_FILES.claims_ledger,
        WORKSPACE_FILES.novelty_ledger,
        WORKSPACE_FILES.terminology,
        WORKSPACE_FILES.supervisor_feedback,
        WORKSPACE_FILES.artefact_registry,
        WORKSPACE_FILES.decisions_md,
        WORKSPACE_FILES.memory_md,
        WORKSPACE_FILES.context_changelog_md,
    ]
    return [name for name in names if (workspace / name).exists()]


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists meta (
            key text primary key,
            value text not null
        );
        create table if not exists sync_files (
            relative_path text primary key,
            sha256 text not null,
            size_bytes integer not null,
            mtime real not null,
            last_synced_at text not null,
            db_revision integer not null,
            file_revision integer not null,
            dirty_flag integer not null default 0,
            conflict_status text not null default 'clean',
            file_kind text not null
        );
        create table if not exists pending_changes (
            id integer primary key autoincrement,
            relative_path text not null,
            proposed_content text not null,
            reason text not null,
            created_at text not null,
            applied_at text,
            status text not null default 'pending'
        );
        create table if not exists memory_entries (
            id integer primary key autoincrement,
            category text not null,
            key text not null,
            value_json text not null,
            created_at text not null,
            updated_at text not null,
            unique(category, key)
        );
        create table if not exists document_aliases (
            alias text primary key,
            target_kind text not null,
            target_value text not null,
            source text not null,
            updated_at text not null
        );
        create table if not exists fts_index (
            id integer primary key autoincrement,
            doc_kind text not null,
            doc_id text not null,
            path text,
            text_excerpt text not null,
            updated_at text not null,
            unique(doc_kind, doc_id)
        );
        create virtual table if not exists fts_index_search using fts5(doc_kind, doc_id, path, text_excerpt);
        """
    )


def _sync_memory_defaults(conn: sqlite3.Connection, now: str) -> None:
    defaults = [
        ("search_history", "initialized", {"notes": "Search query memory is ready for future runs."}),
        ("query_patterns", "successful", {"patterns": []}),
        ("query_patterns", "weak", {"patterns": []}),
        ("user_preferences", "workspace", {"source": "workspace_config"}),
        ("guideline_decisions", "default", {"decisions": []}),
        ("citation_decisions", "default", {"decisions": []}),
        ("validation_notes", "default", {"notes": []}),
        ("claim_source_links", "default", {"links": []}),
        ("ai_safe_context_choices", "default", {"choices": []}),
    ]
    for category, key, value in defaults:
        conn.execute(
            """
            insert into memory_entries (category, key, value_json, created_at, updated_at)
            values (?, ?, ?, ?, ?)
            on conflict(category, key) do update set updated_at = excluded.updated_at
            """,
            (category, key, json.dumps(value, sort_keys=True), now, now),
        )


def _sync_document_aliases(conn: sqlite3.Connection, workspace: Path, now: str) -> None:
    for alias, relative_dir in PRIMARY_OUTPUT_ALIASES.items():
        conn.execute(
            """
            insert into document_aliases (alias, target_kind, target_value, source, updated_at)
            values (?, 'primary_output_alias', ?, 'built_in', ?)
            on conflict(alias) do update set target_value = excluded.target_value, updated_at = excluded.updated_at
            """,
            (alias, relative_dir, now),
        )
    for artefact in list_artefacts(workspace):
        artefact_id = str(artefact.get("id") or "").strip()
        title = str(artefact.get("title") or "").strip()
        path = str(artefact.get("path") or "").strip()
        if artefact_id and path:
            _upsert_alias(conn, artefact_id, "artefact_id", path, "artefact_registry", now)
        if title and path:
            _upsert_alias(conn, title.lower(), "artefact_title", path, "artefact_registry", now)


def _sync_fts_indexes(conn: sqlite3.Connection, workspace: Path, now: str) -> None:
    conn.execute("delete from fts_index_search")
    for doc in _fts_documents(workspace):
        conn.execute(
            """
            insert into fts_index (doc_kind, doc_id, path, text_excerpt, updated_at)
            values (?, ?, ?, ?, ?)
            on conflict(doc_kind, doc_id) do update set
                path = excluded.path,
                text_excerpt = excluded.text_excerpt,
                updated_at = excluded.updated_at
            """,
            (doc["doc_kind"], doc["doc_id"], doc["path"], doc["text_excerpt"], now),
        )
        conn.execute(
            "insert into fts_index_search (doc_kind, doc_id, path, text_excerpt) values (?, ?, ?, ?)",
            (doc["doc_kind"], doc["doc_id"], doc["path"], doc["text_excerpt"]),
        )


def _fts_documents(workspace: Path) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    for base, kind in [
        (workspace / "sources_text", "converted_source_text"),
        (workspace / "artefacts", "artefact_text"),
        (workspace / "guidelines" / "text", "guideline_text"),
    ]:
        if base.is_dir():
            for path in sorted(base.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
                    docs.append(_fts_doc(kind, path, workspace))
    for file_name, key, kind in [
        (WORKSPACE_FILES.claims_ledger, "claims", "claims"),
        (WORKSPACE_FILES.accepted_sources, "source_ids", "references"),
        (WORKSPACE_FILES.research_questions, "research_questions", "document_sections"),
    ]:
        path = workspace / file_name
        if path.exists():
            data = read_yaml(path)
            docs.append(
                {
                    "doc_kind": kind,
                    "doc_id": file_name,
                    "path": file_name,
                    "text_excerpt": json.dumps(data.get(key, data), sort_keys=True)[:4000],
                }
            )
    return docs


def _fts_doc(kind: str, path: Path, workspace: Path) -> dict[str, str]:
    relative = str(path.relative_to(workspace))
    return {
        "doc_kind": kind,
        "doc_id": relative,
        "path": relative,
        "text_excerpt": path.read_text(encoding="utf-8", errors="replace")[:4000],
    }


def _upsert_alias(conn: sqlite3.Connection, alias: str, target_kind: str, target_value: str, source: str, now: str) -> None:
    conn.execute(
        """
        insert into document_aliases (alias, target_kind, target_value, source, updated_at)
        values (?, ?, ?, ?, ?)
        on conflict(alias) do update set
            target_kind = excluded.target_kind,
            target_value = excluded.target_value,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        (alias, target_kind, target_value, source, now),
    )


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "insert into meta (key, value) values (?, ?) on conflict(key) do update set value = excluded.value",
        (key, value),
    )


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("select value from meta where key = ?", (key,)).fetchone()
    return str(row["value"]) if row else None


def _count(conn: sqlite3.Connection, table: str, where: str | None = None) -> int:
    sql = f"select count(*) from {table}"
    if where:
        sql += f" where {where}"
    return int(conn.execute(sql).fetchone()[0])


def _has_pending_change(conn: sqlite3.Connection, relative_path: str) -> bool:
    row = conn.execute(
        "select 1 from pending_changes where relative_path = ? and status = 'pending' limit 1",
        (relative_path,),
    ).fetchone()
    return row is not None


def _text_columns(conn: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [
        row["name"]
        for row in conn.execute("select name from sqlite_master where type = 'table' and name not like 'sqlite_%'")
    ]
    result: dict[str, list[str]] = {}
    for table in tables:
        columns = []
        for column in conn.execute(f"pragma table_info({table})"):
            if "text" in str(column["type"]).lower():
                columns.append(str(column["name"]))
        if columns:
            result[table] = columns
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_kind(relative_path: str) -> str:
    suffix = Path(relative_path).suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".md":
        return "markdown"
    return "other"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
