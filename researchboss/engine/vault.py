from __future__ import annotations

import difflib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from researchboss.core.constants import WORKSPACE_FILES
from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.document_targets import resolve_document_target
from researchboss.engine.filenames import author_token, safe_filename_token
from researchboss.engine.sources import sha256_file


VAULT_DIRS = {
    "originals": "document_vault/originals",
    "versions": "document_vault/versions",
    "derived_text": "document_vault/derived_text",
    "diffs": "document_vault/diffs",
    "manifests": "document_vault/manifests",
    "ai_edit_sessions": "document_vault/ai_edit_sessions",
    "upload_originals": "document_vault/uploads/originals",
    "upload_renamed": "document_vault/uploads/renamed",
}

TEXT_LIKE_EXTENSIONS = {".txt", ".md"}


def vault_layout(workspace: Path) -> dict[str, Path]:
    return {name: workspace / rel for name, rel in VAULT_DIRS.items()}


def ensure_vault_dirs(workspace: Path) -> dict[str, Path]:
    layout = vault_layout(workspace)
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def list_document_versions(workspace: Path, target: Optional[str] = None) -> list[dict[str, Any]]:
    versions = _read_ledger(workspace).get("versions", [])
    if target is None:
        return versions
    resolved = resolve_document_target(workspace, target)
    target_key = str(resolved.path)
    return [record for record in versions if record.get("target_path") == target_key]


def create_document_version(
    workspace: Path,
    target: str,
    *,
    creation_reason: str = "manual_snapshot",
    source_command: Optional[str] = None,
    model_metadata: Optional[dict[str, Any]] = None,
    guideline_ids: Optional[list[str]] = None,
    validation_report_id: Optional[str] = None,
    citation_plan_id: Optional[str] = None,
    parent_version_id: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> dict[str, Any]:
    layout = ensure_vault_dirs(workspace)
    resolved = resolve_document_target(workspace, target, cwd=cwd)
    if not resolved.path.is_file():
        raise ValueError(f"Document target file does not exist: {resolved.path}")

    versions = _read_ledger(workspace).get("versions", [])
    target_key = str(resolved.path)
    latest = _latest_version_for_target(versions, target_key)
    content_hash = sha256_file(resolved.path)

    if (
        parent_version_id is None
        and latest is not None
        and latest.get("content_hash") == content_hash
        and creation_reason == "manual_snapshot"
    ):
        return latest

    resolved_parent_id = parent_version_id or (latest.get("version_id") if latest else None)
    is_first_version_for_target = resolved_parent_id is None

    version_id = f"docv-{len(versions) + 1:03d}"
    extension = resolved.path.suffix
    stored_path = layout["versions"] / f"{version_id}{extension}"
    shutil.copy2(resolved.path, stored_path)

    if is_first_version_for_target:
        original_copy = layout["originals"] / f"{version_id}{extension}"
        shutil.copy2(resolved.path, original_copy)

    record = {
        "version_id": version_id,
        "target": resolved.target,
        "target_path": target_key,
        "target_kind": resolved.kind,
        "artefact_id": resolved.artefact_id,
        "parent_version_id": resolved_parent_id,
        "stored_path": str(stored_path),
        "content_hash": content_hash,
        "creation_reason": creation_reason,
        "source_command": source_command,
        "model_metadata": model_metadata or {},
        "guideline_ids": guideline_ids or [],
        "validation_report_id": validation_report_id,
        "citation_plan_id": citation_plan_id,
        "created_at": _utc_now(),
        "original_file_modified": False,
    }
    write_yaml(layout["manifests"] / f"{version_id}.yaml", dict(record, version=1))

    ledger = _read_ledger(workspace)
    ledger.setdefault("versions", []).append(record)
    _write_ledger(workspace, ledger)
    return record


def diff_document_versions(workspace: Path, version_id_a: str, version_id_b: str) -> dict[str, Any]:
    layout = ensure_vault_dirs(workspace)
    version_a = _get_version(workspace, version_id_a)
    version_b = _get_version(workspace, version_id_b)
    path_a = Path(str(version_a["stored_path"]))
    path_b = Path(str(version_b["stored_path"]))

    if path_a.suffix.lower() not in TEXT_LIKE_EXTENSIONS or path_b.suffix.lower() not in TEXT_LIKE_EXTENSIONS:
        report = {
            "version": 1,
            "version_id_a": version_id_a,
            "version_id_b": version_id_b,
            "diff_supported": False,
            "reason": "Diff is only supported when both versions are plain text or Markdown.",
            "changed": None,
            "lines": [],
        }
    else:
        text_a = path_a.read_text(encoding="utf-8", errors="replace").splitlines()
        text_b = path_b.read_text(encoding="utf-8", errors="replace").splitlines()
        diff_lines = list(
            difflib.unified_diff(text_a, text_b, fromfile=version_id_a, tofile=version_id_b, lineterm="")
        )
        report = {
            "version": 1,
            "version_id_a": version_id_a,
            "version_id_b": version_id_b,
            "diff_supported": True,
            "reason": None,
            "changed": text_a != text_b,
            "lines": diff_lines,
        }

    diff_path = layout["diffs"] / f"{version_id_a}__{version_id_b}.yaml"
    write_yaml(diff_path, report)
    report["diff_path"] = str(diff_path)
    return report


def compare_document_versions(workspace: Path, version_id_a: str, version_id_b: str) -> dict[str, Any]:
    layout = ensure_vault_dirs(workspace)
    version_a = _get_version(workspace, version_id_a)
    version_b = _get_version(workspace, version_id_b)
    report_a = _validation_report_for_version(workspace, version_a)
    report_b = _validation_report_for_version(workspace, version_b)

    if report_a is None or report_b is None:
        comparison = {
            "version": 1,
            "version_id_a": version_id_a,
            "version_id_b": version_id_b,
            "comparable": False,
            "reason": "Both versions must have a linked validation report to compare strengths, weaknesses, and references.",
            "strengths": None,
            "weaknesses": None,
            "unsupported_claims": None,
            "weakly_supported_claims": None,
            "references": None,
        }
    else:
        comparison = {
            "version": 1,
            "version_id_a": version_id_a,
            "version_id_b": version_id_b,
            "comparable": True,
            "reason": None,
            "strengths": _kind_list_diff(report_a.get("strengths"), report_b.get("strengths")),
            "weaknesses": _kind_list_diff(report_a.get("weaknesses"), report_b.get("weaknesses")),
            "unsupported_claims": _claim_text_diff(report_a.get("unsupported_claims"), report_b.get("unsupported_claims")),
            "weakly_supported_claims": _claim_text_diff(
                report_a.get("weakly_supported_claims"), report_b.get("weakly_supported_claims")
            ),
            "references": _reference_diff(report_a.get("references"), report_b.get("references")),
        }

    comparison_path = layout["diffs"] / f"version-comparison-{version_id_a}__{version_id_b}.yaml"
    write_yaml(comparison_path, comparison)
    comparison["comparison_path"] = str(comparison_path)
    return comparison


def _validation_report_for_version(workspace: Path, version: dict[str, Any]) -> Optional[dict[str, Any]]:
    report_id = version.get("validation_report_id")
    if not report_id:
        return None
    path = workspace / "outputs" / "validation" / f"{report_id}.yaml"
    if not path.is_file():
        return None
    report = read_yaml(path)
    return report if isinstance(report, dict) else None


def _kind_list_diff(before: Any, after: Any) -> dict[str, list[str]]:
    before_kinds = {str(item.get("kind")) for item in (before or []) if isinstance(item, dict) and item.get("kind")}
    after_kinds = {str(item.get("kind")) for item in (after or []) if isinstance(item, dict) and item.get("kind")}
    return {"added": sorted(after_kinds - before_kinds), "removed": sorted(before_kinds - after_kinds)}


def _claim_text_diff(before: Any, after: Any) -> dict[str, list[str]]:
    before_texts = {str(item.get("text")) for item in (before or []) if isinstance(item, dict) and item.get("text")}
    after_texts = {str(item.get("text")) for item in (after or []) if isinstance(item, dict) and item.get("text")}
    return {"added": sorted(after_texts - before_texts), "removed": sorted(before_texts - after_texts)}


def _reference_diff(before: Any, after: Any) -> dict[str, list[str]]:
    def _reference_lines(value: Any) -> set[str]:
        accepted = value.get("accepted_workspace_evidence") if isinstance(value, dict) else []
        return {
            str(item.get("reference"))
            for item in (accepted or [])
            if isinstance(item, dict) and item.get("reference")
        }

    before_lines = _reference_lines(before)
    after_lines = _reference_lines(after)
    return {"added": sorted(after_lines - before_lines), "removed": sorted(before_lines - after_lines)}


def restore_document_version(
    workspace: Path,
    version_id: str,
    *,
    output_path: Optional[Path] = None,
) -> dict[str, Any]:
    version = _get_version(workspace, version_id)
    stored_path = Path(str(version["stored_path"]))
    if not stored_path.is_file():
        raise ValueError(f"Stored version file is missing: {stored_path}")

    target_path = Path(str(version["target_path"]))
    extension = target_path.suffix
    default_output = target_path.parent / f"{target_path.stem}.restored-{version_id}{extension}"
    destination = (output_path or default_output).expanduser()
    if destination.exists():
        raise ValueError(f"Restore destination already exists: {destination}. Choose a different --output path.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stored_path, destination)

    record = create_document_version(
        workspace,
        str(destination),
        creation_reason="restore",
        source_command="doc restore",
        parent_version_id=version_id,
    )
    record["restored_from_version_id"] = version_id
    record["restored_to_path"] = str(destination)
    return record


def list_uploaded_artefacts(workspace: Path) -> list[dict[str, Any]]:
    return _read_ledger(workspace).get("uploads", [])


def intake_uploaded_artefact(
    workspace: Path,
    source_path: Path,
    *,
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[str] = None,
) -> dict[str, Any]:
    """Copy an externally created artefact into the document vault under a sanitized name.

    `source_path` is only ever read and copied — never modified, moved, or
    deleted. Both the original upload and a renamed working copy are kept, so
    the mapping between the two is always recoverable. The renamed filename
    embeds the upload ID, mirroring the source filename-suggestion pattern's
    use of source_id, which avoids collisions by construction; the separate
    original-copy directory (where filenames are not disambiguated by an ID)
    still gets a numeric suffix if a same-named file was uploaded before.
    """
    if not source_path.is_file():
        raise ValueError(f"Uploaded artefact does not exist: {source_path}")

    layout = ensure_vault_dirs(workspace)
    ledger = _read_ledger(workspace)
    uploads = ledger.setdefault("uploads", [])

    upload_id = f"upload-{len(uploads) + 1:03d}"
    extension = source_path.suffix.lower().lstrip(".") or "bin"
    title_value = (title or source_path.stem).strip() or "untitled"
    year_value = str(year).strip() if year else "nd"
    title_tok = safe_filename_token(title_value, fallback="untitled")
    author_tok = safe_filename_token(author_token([author] if author else []), fallback="unknown-author")

    renamed_name = f"{author_tok}_{year_value}_{title_tok}_{upload_id}.{extension}"[:200]
    renamed_path = layout["upload_renamed"] / renamed_name
    shutil.copy2(source_path, renamed_path)

    original_copy_path = _collision_safe_path(layout["upload_originals"] / source_path.name)
    shutil.copy2(source_path, original_copy_path)

    record = {
        "upload_id": upload_id,
        "original_uploaded_path": str(source_path),
        "original_file_name": source_path.name,
        "vault_original_copy_path": str(original_copy_path),
        "vault_renamed_path": str(renamed_path),
        "renamed_file_name": renamed_name,
        "title": title_value,
        "author_token": author_tok,
        "year": year_value,
        "content_hash": sha256_file(source_path),
        "created_at": _utc_now(),
        "original_file_modified": False,
    }
    uploads.append(record)
    ledger["uploads"] = uploads
    _write_ledger(workspace, ledger)
    return record


def _collision_safe_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _get_version(workspace: Path, version_id: str) -> dict[str, Any]:
    for record in list_document_versions(workspace):
        if record.get("version_id") == version_id:
            return record
    raise ValueError(f"Unknown document version_id: {version_id}")


def _latest_version_for_target(versions: list[dict[str, Any]], target_key: str) -> Optional[dict[str, Any]]:
    matches = [record for record in versions if record.get("target_path") == target_key]
    return matches[-1] if matches else None


def _ledger_path(workspace: Path) -> Path:
    return workspace / WORKSPACE_FILES.document_vault_ledger


def _read_ledger(workspace: Path) -> dict[str, Any]:
    ledger = read_yaml(_ledger_path(workspace))
    ledger.setdefault("version", 1)
    ledger.setdefault("versions", [])
    ledger.setdefault("uploads", [])
    return ledger


def _write_ledger(workspace: Path, ledger: dict[str, Any]) -> None:
    write_yaml(_ledger_path(workspace), ledger)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
