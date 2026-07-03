from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchboss.core.yamlio import write_yaml
from researchboss.engine.conversion import CONVERTIBLE_EXTENSIONS, extract_text
from researchboss.engine.document_targets import DocumentTarget, resolve_document_target
from researchboss.engine.sources import list_sources


VALIDATION_STOP_WORDS = {
    "about",
    "after",
    "also",
    "among",
    "based",
    "because",
    "between",
    "could",
    "from",
    "have",
    "into",
    "more",
    "other",
    "over",
    "research",
    "should",
    "such",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "were",
    "when",
    "where",
    "which",
    "with",
    "would",
}


@dataclass(frozen=True)
class DocumentValidationRun:
    report: dict[str, Any]
    yaml_path: Path
    markdown_path: Path


def validate_document(
    workspace: Path,
    target: str,
    *,
    source_paths: list[Path] | None = None,
    cwd: Path | None = None,
) -> DocumentValidationRun:
    resolved_target = resolve_document_target(workspace, target, cwd=cwd)
    target_text = _read_supported_text(resolved_target.path)
    target_terms = _top_terms(target_text)
    source_entries = _validation_sources(workspace, source_paths=source_paths or [])
    comparisons = [_compare_source(target_terms, source) for source in source_entries]

    report = {
        "version": 1,
        "validation_method": "deterministic_term_overlap",
        "ai_used": False,
        "target": _target_record(resolved_target, target_text, target_terms),
        "summary": _summary(comparisons),
        "sources": comparisons,
        "limitations": [
            "This deterministic report compares vocabulary overlap only.",
            "It does not prove claim support, contradiction, novelty, or citation correctness.",
            "Unknown source metadata is preserved as unknown.",
        ],
    }
    yaml_path = _report_path(workspace, resolved_target.path, ".yaml")
    markdown_path = _report_path(workspace, resolved_target.path, ".md")
    write_yaml(yaml_path, report)
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return DocumentValidationRun(report=report, yaml_path=yaml_path, markdown_path=markdown_path)


def _validation_sources(workspace: Path, *, source_paths: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for source in list_sources(workspace, status="accepted"):
        entries.append(_workspace_source_entry(source))

    for index, path in enumerate(source_paths, start=1):
        resolved = path.expanduser().resolve()
        entries.append(
            {
                "source_id": f"explicit-source-{index:03d}",
                "source_kind": "explicit_path",
                "status": "explicit",
                "provider": "user_supplied_path",
                "title": resolved.name,
                "authors": "Unknown",
                "year": "Unknown",
                "doi": "Unknown",
                "path": str(resolved),
            }
        )
    return entries


def _workspace_source_entry(source: dict[str, Any]) -> dict[str, Any]:
    metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
    conversion = source.get("conversion") if isinstance(source.get("conversion"), dict) else {}
    output_path = conversion.get("output_path")
    path = str(output_path or source.get("file_path") or "")
    return {
        "source_id": str(source.get("source_id") or "Unknown"),
        "source_kind": "workspace_source",
        "status": str(source.get("status") or "Unknown"),
        "provider": str(source.get("provider") or "Unknown"),
        "title": _unknown(source.get("zotero_title") or metadata.get("title") or source.get("file_name")),
        "authors": _unknown(source.get("zotero_creators") or metadata.get("authors")),
        "year": _unknown(source.get("zotero_year") or metadata.get("year")),
        "doi": _unknown(source.get("zotero_doi") or metadata.get("doi")),
        "path": path,
    }


def _compare_source(target_terms: list[str], source: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(source.get("path") or ""))
    record = {key: value for key, value in source.items() if key != "path"}
    record["path"] = str(source_path)
    record["text_available"] = False
    record["overlap_score"] = 0.0
    record["matched_terms"] = []
    record["missing_text_reason"] = None

    try:
        source_text = _read_supported_text(source_path)
    except Exception as exc:
        record["missing_text_reason"] = str(exc)
        return record

    source_terms = set(_top_terms(source_text, limit=100))
    matched_terms = [term for term in target_terms if term in source_terms]
    record["text_available"] = True
    record["overlap_score"] = round(len(matched_terms) / max(len(target_terms), 1), 4)
    record["matched_terms"] = matched_terms[:25]
    return record


def _read_supported_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise ValueError(f"Document text path is missing: {path}")
    if path.suffix.lower() not in CONVERTIBLE_EXTENSIONS:
        raise ValueError(f"Unsupported document extension for deterministic validation: {path.suffix.lower()}")
    return extract_text(path)


def _top_terms(text: str, *, limit: int = 50) -> list[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text)
        if token.lower() not in VALIDATION_STOP_WORDS
    ]
    counts = Counter(tokens)
    return [term for term, _count in counts.most_common(limit)]


def _target_record(target: DocumentTarget, text: str, terms: list[str]) -> dict[str, Any]:
    return {
        "requested": target.target,
        "kind": target.kind,
        "source": target.source,
        "path": str(target.path),
        "artefact_id": target.artefact_id,
        "artefact_title": target.artefact_title,
        "artefact_type": target.artefact_type,
        "character_count": len(text),
        "top_terms": terms,
    }


def _summary(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(item["overlap_score"]) for item in comparisons if item.get("text_available")]
    return {
        "source_count": len(comparisons),
        "sources_with_text": sum(1 for item in comparisons if item.get("text_available")),
        "sources_without_text": sum(1 for item in comparisons if not item.get("text_available")),
        "sources_with_overlap": sum(1 for item in comparisons if float(item.get("overlap_score") or 0) > 0),
        "average_overlap_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
    }


def _report_path(workspace: Path, target_path: Path, suffix: str) -> Path:
    stem = _safe_slug(target_path.stem) or "target"
    return workspace / "outputs" / "validation" / f"document-validation-{stem}{suffix}"


def _markdown_report(report: dict[str, Any]) -> str:
    target = report["target"]
    summary = report["summary"]
    lines = [
        f"# Document Validation: {Path(str(target['path'])).name}",
        "",
        "- Validation method: Deterministic term overlap",
        "- AI used: No",
        f"- Target: {target['path']}",
        "",
        "## Summary",
        "",
        f"- Sources compared: {summary['source_count']}",
        f"- Sources with text: {summary['sources_with_text']}",
        f"- Sources without text: {summary['sources_without_text']}",
        f"- Sources with overlap: {summary['sources_with_overlap']}",
        f"- Average overlap score: {summary['average_overlap_score']}",
        "",
        "## Source Matches",
        "",
        "| Source ID | Provider | Title | Text available | Overlap score | Matched terms |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for source in report["sources"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(source.get("source_id") or "Unknown"),
                    str(source.get("provider") or "Unknown"),
                    _escape_table(str(source.get("title") or "Unknown")),
                    "Yes" if source.get("text_available") else "No",
                    str(source.get("overlap_score") or 0),
                    ", ".join(source.get("matched_terms") or []) or "None",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"


def _unknown(value: Any) -> str:
    if value in (None, "", []):
        return "Unknown"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "Unknown"
    return str(value)


def _safe_slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return re.sub(r"-+", "-", slug)


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")
