from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchboss.core.yamlio import write_yaml


ABSTRACT_EXTENSIONS = {".txt"}


@dataclass(frozen=True)
class AbstractImportResult:
    processed: int
    candidate: int
    filtered: int
    skipped: int
    register_path: Path


def parse_legacy_scopus_abstract(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fields: dict[str, Any] = {"source_path": str(path)}
    patterns = {
        "title": r"(?im)^\s*(?:Title|Document Title)\s*:\s*(.+)$",
        "authors": r"(?im)^\s*(?:Authors?|Author\(s\))\s*:\s*(.+)$",
        "publication_title": r"(?im)^\s*(?:Publication|Source title|Journal)\s*:\s*(.+)$",
        "year": r"(?im)^\s*(?:Year|Publication Year)\s*:\s*(\d{4})\b",
        "doi": r"(?im)^\s*DOI\s*:\s*(.+)$",
        "cited_by_count": r"(?im)^\s*(?:Cited by|Cited-by count)\s*:\s*(\d+)\b",
        "api_url": r"(?im)^\s*(?:API URL|Scopus API URL)\s*:\s*(.+)$",
        "scopus_url": r"(?im)^\s*(?:Scopus URL|Scopus view URL)\s*:\s*(.+)$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            fields[key] = match.group(1).strip()
    abstract = _abstract_block(text)
    if abstract:
        fields["abstract"] = abstract
    if isinstance(fields.get("authors"), str):
        fields["authors"] = [part.strip() for part in re.split(r";|,\s+(?=[A-Z][A-Za-z-]+,\s)", fields["authors"]) if part.strip()]
    if fields.get("cited_by_count") is not None:
        fields["cited_by_count"] = int(fields["cited_by_count"])
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


def import_abstract_folder(workspace: Path, folder: Path) -> AbstractImportResult:
    rows = []
    processed = candidate = filtered = skipped = 0
    for path in sorted(folder.expanduser().glob("*")):
        if not path.is_file():
            continue
        processed += 1
        if path.suffix.lower() not in ABSTRACT_EXTENSIONS:
            skipped += 1
            rows.append({"status": "skipped", "reason": "unsupported_extension", "source_path": str(path)})
            continue
        record = parse_legacy_scopus_abstract(path)
        record["candidate_id"] = _abstract_candidate_id(record)
        missing = [field for field in ("title", "abstract") if not record.get(field)]
        if missing:
            filtered += 1
            record.update({"status": "filtered", "filter_reasons": [f"missing_{field}" for field in missing]})
        else:
            candidate += 1
            record.update({"status": "candidate", "filter_reasons": []})
        rows.append(record)

    register = {
        "version": 1,
        "source_folder": str(folder),
        "processed": processed,
        "candidate_count": candidate,
        "filtered_count": filtered,
        "skipped_count": skipped,
        "candidates": [row for row in rows if row.get("status") == "candidate"],
        "filtered": [row for row in rows if row.get("status") == "filtered"],
        "skipped": [row for row in rows if row.get("status") == "skipped"],
        "selected_for_review": [],
        "not_relevant": [],
        "notes": "Abstract import never moves, deletes, or edits original abstract files.",
    }
    register_path = workspace / "outputs" / "recommendations" / "abstract-candidates.yaml"
    write_yaml(register_path, register)
    return AbstractImportResult(
        processed=processed,
        candidate=candidate,
        filtered=filtered,
        skipped=skipped,
        register_path=register_path,
    )


def _abstract_block(text: str) -> str | None:
    match = re.search(r"(?ims)^\s*Abstract\s*:\s*(.+?)(?:\n\s*[A-Z][A-Za-z -]{1,30}\s*:|\Z)", text)
    if not match:
        return None
    return " ".join(match.group(1).split())


def _abstract_candidate_id(record: dict[str, Any]) -> str:
    basis = "|".join(str(record.get(key) or "") for key in ("title", "year", "doi", "source_path"))
    return f"abs-{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:12]}"
