from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.filenames import author_token as _author_token
from researchboss.engine.filenames import safe_filename_token as _safe_filename_token


DOI_VALUE_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
DOI_URL_RE = re.compile(r"https?://(?:dx\.)?doi\.org/(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip().rstrip(".,;)")
    match = DOI_URL_RE.search(text)
    if match:
        return match.group(1).rstrip(".,;)").lower()
    if text.lower().startswith("doi:"):
        text = text[4:].strip()
    return text.lower() if DOI_VALUE_RE.match(text) else None


def validate_source_doi(source: dict[str, Any]) -> dict[str, Any]:
    metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
    raw_doi = metadata.get("doi") or source.get("zotero_doi")
    raw_url = metadata.get("url") or source.get("zotero_url")
    normalized_doi = normalize_doi(str(raw_doi)) if raw_doi else None
    url_doi = normalize_doi(str(raw_url)) if raw_url else None
    issues = []
    if raw_doi and not normalized_doi:
        issues.append("malformed_doi")
    if raw_url and "doi.org" in str(raw_url).lower() and not url_doi:
        issues.append("malformed_doi_url")
    if normalized_doi and url_doi and normalized_doi != url_doi:
        issues.append("doi_url_mismatch")
    return {
        "source_id": source.get("source_id"),
        "raw_doi": raw_doi,
        "normalized_doi": normalized_doi,
        "raw_url": raw_url,
        "url_doi": url_doi,
        "status": "ok" if not issues else "needs_review",
        "issues": issues,
    }


def citation_consistency_report(workspace: Path) -> dict[str, Any]:
    sources = _sources(workspace)
    rows = []
    for source in sources:
        metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
        missing = []
        for field in ("title", "year", "doi", "creators"):
            value = metadata.get(field) or source.get(f"zotero_{field}")
            if value in (None, "", []):
                missing.append(field)
        doi_check = validate_source_doi(source)
        rows.append(
            {
                "source_id": source.get("source_id"),
                "file_name": source.get("file_name"),
                "missing_fields": missing,
                "doi_validation": doi_check,
                "status": "ok" if not missing and doi_check["status"] == "ok" else "needs_review",
            }
        )
    report = {"version": 1, "source_count": len(rows), "sources": rows}
    write_yaml(workspace / "outputs" / "validation" / "citation-consistency.yaml", report)
    return report


def duplicate_metadata_report(workspace: Path) -> dict[str, Any]:
    sources = _sources(workspace)
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for source in sources:
        metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
        values = {
            "file_name": source.get("file_name"),
            "title": metadata.get("title") or source.get("zotero_title"),
            "doi": normalize_doi(str(metadata.get("doi") or source.get("zotero_doi") or "")),
        }
        for kind, value in values.items():
            if value:
                buckets.setdefault((kind, str(value).lower()), []).append(source)
    duplicates = [
        {
            "match_type": kind,
            "match_value": value,
            "source_ids": [str(source.get("source_id")) for source in bucket],
        }
        for (kind, value), bucket in sorted(buckets.items())
        if len(bucket) > 1
    ]
    report = {"version": 1, "duplicate_groups": duplicates}
    write_yaml(workspace / "outputs" / "validation" / "metadata-duplicates.yaml", report)
    return report


def build_keyword_index(workspace: Path) -> dict[str, Any]:
    register = read_yaml(workspace / "source-register.yaml")
    sources = [source for source in register.get("sources", []) if isinstance(source, dict)]
    entries = []
    for source in sources:
        conversion = source.get("conversion") if isinstance(source.get("conversion"), dict) else {}
        output_path = conversion.get("output_path")
        if not output_path or not Path(str(output_path)).is_file():
            continue
        text = Path(str(output_path)).read_text(encoding="utf-8", errors="replace")
        counts: dict[str, int] = {}
        for token in TOKEN_RE.findall(text.lower()):
            if len(token) < 3:
                continue
            counts[token] = counts.get(token, 0) + 1
        entries.append(
            {
                "source_id": source.get("source_id"),
                "output_path": str(output_path),
                "token_count": sum(counts.values()),
                "terms": dict(sorted(counts.items())),
            }
        )
    index = {"version": 1, "entry_count": len(entries), "entries": entries}
    write_yaml(workspace / "sources_metadata" / "keyword-index.yaml", index)
    return index


def filename_suggestion_report(workspace: Path) -> dict[str, Any]:
    rows = []
    for source in _sources(workspace):
        rows.append(_filename_suggestion(source))
    report = {
        "version": 1,
        "source_count": len(rows),
        "suggestions": rows,
        "original_files_renamed": False,
        "notes": "Suggestions are deterministic only; ResearchBoss does not rename or move original files.",
    }
    write_yaml(workspace / "outputs" / "recommendations" / "filename-suggestions.yaml", report)
    return report


def _filename_suggestion(source: dict[str, Any]) -> dict[str, Any]:
    metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
    title = source.get("zotero_title") or metadata.get("title") or Path(str(source.get("file_name") or "source")).stem
    authors = source.get("zotero_creators") or metadata.get("authors") or metadata.get("creators") or []
    if isinstance(authors, str):
        authors = [authors]
    author_token = _safe_filename_token(_author_token(authors), fallback="unknown-author")
    title_token = _safe_filename_token(str(title), fallback="untitled")
    year = str(source.get("zotero_year") or metadata.get("year") or "nd")
    source_id = _safe_filename_token(str(source.get("source_id") or "source"), fallback="source")
    extension = str(source.get("file_ext") or Path(str(source.get("file_name") or "")).suffix.lstrip(".") or "pdf").lower()
    suggested = f"{author_token}_{year}_{title_token}_{source_id}.{extension}"
    return {
        "source_id": source.get("source_id"),
        "current_file_name": source.get("file_name"),
        "suggested_file_name": suggested[:180],
        "basis": {
            "author_token": author_token,
            "year": year,
            "title": title,
            "source_id": source.get("source_id"),
            "extension": extension,
        },
        "rename_performed": False,
    }


def _sources(workspace: Path) -> list[dict[str, Any]]:
    register = read_yaml(workspace / "source-register.yaml")
    return [source for source in register.get("sources", []) if isinstance(source, dict)]
