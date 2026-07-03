from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.zotero import (
    attachment_metadata_by_storage_key,
    has_zotero_fulltext_cache,
    zotero_relative_path,
    zotero_storage_key,
)


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".sqlite", ".db"}
SOURCE_STATUSES = {"pending_review", "accepted", "ignored", "maybe"}
REVIEW_STATUSES = {"accepted", "ignored", "maybe"}
INITIAL_SOURCE_STATUSES = {"pending_review", "maybe"}


@dataclass(frozen=True)
class ScanResult:
    processed: int
    added: int
    duplicates: int
    skipped: int


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_source_files(root: Path) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in ALLOWED_EXTENSIONS:
                yield p


def _load_register(workspace: Path) -> dict[str, Any]:
    return read_yaml(workspace / "source-register.yaml")


def _write_register(workspace: Path, reg: dict[str, Any]) -> None:
    write_yaml(workspace / "source-register.yaml", reg)


def _existing_hashes(reg: dict[str, Any]) -> set[str]:
    hashes: set[str] = set()
    for s in reg.get("sources", []):
        if isinstance(s, dict) and s.get("content_hash"):
            hashes.add(s["content_hash"])
    return hashes


def _make_source_id(file_path: Path, content_hash: str) -> str:
    stem = "".join(ch for ch in file_path.stem.lower() if ch.isalnum() or ch in ("-", "_"))
    stem = stem[:24] if stem else "source"
    return f"{stem}__{content_hash[:10]}"


def validate_source_status(status: str) -> None:
    if status not in SOURCE_STATUSES:
        allowed = ", ".join(sorted(SOURCE_STATUSES))
        raise ValueError(f"Invalid source status: {status!r}. Expected one of: {allowed}")


def scan_sources(
    workspace: Path,
    source_root: Path,
    *,
    provider: str = "local_folder",  # local_folder | zotero_storage
    logger: Optional[Any] = None,
    file_paths: Optional[list[Path]] = None,
    initial_status: str = "pending_review",
    zotero_root: Optional[Path] = None,
) -> ScanResult:
    if initial_status not in INITIAL_SOURCE_STATUSES:
        allowed = ", ".join(sorted(INITIAL_SOURCE_STATUSES))
        raise ValueError(f"Invalid initial source status: {initial_status!r}. Expected one of: {allowed}")

    reg = _load_register(workspace)
    reg.setdefault("version", 1)
    reg.setdefault("sources", [])
    maybe = read_yaml(workspace / "maybe-sources.yaml")
    maybe.setdefault("source_ids", [])

    seen_hashes = _existing_hashes(reg)

    processed = added = duplicates = skipped = 0

    paths = file_paths if file_paths is not None else list(iter_source_files(source_root))

    for p in paths:
        processed += 1
        try:
            content_hash = sha256_file(p)
        except Exception as e:  # Phase 1: do not fake success
            skipped += 1
            if logger:
                logger.error("Failed to hash file; skipping", file_path=str(p), error=str(e))
            continue

        if content_hash in seen_hashes:
            duplicates += 1
            if logger:
                logger.info("Duplicate detected by hash; not adding", file_path=str(p), content_hash=content_hash)
            continue

        source_id = _make_source_id(p, content_hash)
        record = {
            "source_id": source_id,
            "provider": provider,
            "file_path": str(p),
            "file_name": p.name,
            "file_ext": p.suffix.lower().lstrip("."),
            "content_hash": content_hash,
            "status": initial_status,
            "discovered_at": None,  # fill later with timestamps in Phase 2+ if desired
            "notes": None,
        }
        if provider == "zotero_storage":
            storage_key = zotero_storage_key(p, source_root)
            record.update(
                {
                    "zotero_storage_key": storage_key,
                    "zotero_relative_path": zotero_relative_path(p, source_root),
                    "has_zotero_fulltext_cache": has_zotero_fulltext_cache(p, source_root),
                }
            )
            if zotero_root and storage_key:
                metadata = attachment_metadata_by_storage_key(zotero_root, storage_key)
                if metadata:
                    record.update(metadata.as_source_fields())
        reg["sources"].append(record)
        if initial_status == "maybe":
            maybe["source_ids"].append(source_id)
        seen_hashes.add(content_hash)
        added += 1

        if logger:
            logger.info("Discovered new source (pending_review)", source_id=source_id, file_path=str(p))

    _write_register(workspace, reg)
    if initial_status == "maybe":
        write_yaml(workspace / "maybe-sources.yaml", maybe)
    return ScanResult(processed=processed, added=added, duplicates=duplicates, skipped=skipped)


def list_sources(workspace: Path, *, status: Optional[str] = None) -> list[dict[str, Any]]:
    if status is not None:
        validate_source_status(status)

    reg = _load_register(workspace)
    sources: list[dict[str, Any]] = [s for s in reg.get("sources", []) if isinstance(s, dict)]
    if status:
        sources = [s for s in sources if s.get("status") == status]
    return sources


def set_source_status(
    workspace: Path,
    *,
    source_id: str,
    new_status: str,
    ignore_reason: Optional[str] = None,
) -> None:
    if new_status not in REVIEW_STATUSES:
        allowed = ", ".join(sorted(REVIEW_STATUSES))
        raise ValueError(f"Invalid review status: {new_status!r}. Expected one of: {allowed}")

    reg = _load_register(workspace)
    sources: list[dict[str, Any]] = [s for s in reg.get("sources", []) if isinstance(s, dict)]

    found = False
    for s in sources:
        if s.get("source_id") == source_id:
            s["status"] = new_status
            found = True
            break
    if not found:
        raise ValueError(f"Unknown source_id: {source_id}")

    reg["sources"] = sources
    _write_register(workspace, reg)

    # Maintain convenience lists
    accepted = read_yaml(workspace / "accepted-sources.yaml")
    maybe = read_yaml(workspace / "maybe-sources.yaml")
    ignored = read_yaml(workspace / "ignored-sources.yaml")

    accepted.setdefault("source_ids", [])
    maybe.setdefault("source_ids", [])
    ignored.setdefault("ignored", [])

    def _rm(lst: list[str]) -> list[str]:
        return [x for x in lst if x != source_id]

    accepted["source_ids"] = _rm(list(accepted["source_ids"]))
    maybe["source_ids"] = _rm(list(maybe["source_ids"]))
    ignored["ignored"] = [x for x in ignored["ignored"] if isinstance(x, dict) and x.get("source_id") != source_id]

    if new_status == "accepted":
        accepted["source_ids"].append(source_id)
    elif new_status == "maybe":
        maybe["source_ids"].append(source_id)
    elif new_status == "ignored":
        ignored["ignored"].append({"source_id": source_id, "reason": ignore_reason or ""})

    write_yaml(workspace / "accepted-sources.yaml", accepted)
    write_yaml(workspace / "maybe-sources.yaml", maybe)
    write_yaml(workspace / "ignored-sources.yaml", ignored)


def source_counts(workspace: Path) -> dict[str, int]:
    reg = _load_register(workspace)
    counts: dict[str, int] = {}
    for s in reg.get("sources", []):
        if not isinstance(s, dict):
            continue
        st = s.get("status", "unknown")
        counts[st] = counts.get(st, 0) + 1
    counts["total"] = sum(v for k, v in counts.items() if k != "total")
    return counts
