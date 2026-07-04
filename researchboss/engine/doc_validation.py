from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchboss.core.yamlio import write_yaml
from researchboss.engine.conversion import CONVERTIBLE_EXTENSIONS, extract_text
from researchboss.engine.document_targets import DocumentTarget, resolve_document_target
from researchboss.engine.guidelines import resolve_guidelines
from researchboss.engine.references import apa7_reference
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
    guideline_ids: list[str] | None = None,
    use_default_guidelines: bool = True,
    cwd: Path | None = None,
) -> DocumentValidationRun:
    resolved_target = resolve_document_target(workspace, target, cwd=cwd)
    target_text = _read_supported_text(resolved_target.path)
    target_terms = _top_terms(target_text)
    source_entries = _validation_sources(workspace, source_paths=source_paths or [])
    comparisons = [_compare_source(target_terms, source) for source in source_entries]
    sentence_checks = _sentence_checks(target_text, comparisons)
    guidelines = resolve_guidelines(
        workspace,
        explicit_ids=guideline_ids,
        use_defaults=use_default_guidelines,
        scope="validation",
    )

    report = {
        "version": 1,
        "validation_method": "deterministic_term_overlap",
        "ai_used": False,
        "target": _target_record(resolved_target, target_text, target_terms),
        "guidelines": _guideline_records(guidelines),
        "summary": _summary(comparisons),
        "strengths": _strengths(comparisons, sentence_checks),
        "weaknesses": _weaknesses(comparisons, sentence_checks),
        "unsupported_claims": [item for item in sentence_checks if item["support_status"] == "unsupported"],
        "weakly_supported_claims": [item for item in sentence_checks if item["support_status"] == "weak"],
        "possible_contradictions": _possible_contradictions(),
        "missing_citations": _missing_citations(sentence_checks),
        "candidate_supporting_sources": _candidate_supporting_sources(comparisons),
        "evidence_confidence": _evidence_confidence(comparisons),
        "references": _references(comparisons),
        "human_review_checklist": _human_review_checklist(),
        "sources": comparisons,
        "sentence_checks": sentence_checks,
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
                "publication_venue": "Unknown",
                "paper_type": "Unknown",
                "citation_count": "Unknown",
                "path": str(resolved),
            }
        )
    return entries


def _guideline_records(guidelines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": guideline.get("id"),
            "title": guideline.get("title"),
            "scopes": guideline.get("scopes") or [],
            "precedence": guideline.get("precedence"),
            "selection_source": guideline.get("selection_source"),
            "text_path": guideline.get("text_path"),
        }
        for guideline in guidelines
    ]


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
        "publication_venue": _unknown(
            source.get("zotero_publication_title")
            or metadata.get("publication_title")
            or metadata.get("journal")
            or metadata.get("venue")
        ),
        "paper_type": _unknown(source.get("zotero_item_type") or metadata.get("item_type") or metadata.get("document_type")),
        "citation_count": _unknown(source.get("citation_count") or source.get("cited_by_count")),
        "path": path,
    }


def _compare_source(target_terms: list[str], source: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(source.get("path") or ""))
    record = {key: value for key, value in source.items() if key != "path"}
    record["path"] = str(source_path)
    record["text_available"] = False
    record["overlap_score"] = 0.0
    record["matched_terms"] = []
    record["source_terms"] = []
    record["missing_text_reason"] = None

    try:
        source_text = _read_supported_text(source_path)
    except Exception as exc:
        record["missing_text_reason"] = str(exc)
        return record

    source_terms = _top_terms(source_text, limit=100)
    matched_terms = [term for term in target_terms if term in source_terms]
    record["text_available"] = True
    record["overlap_score"] = round(len(matched_terms) / max(len(target_terms), 1), 4)
    record["matched_terms"] = matched_terms[:25]
    record["source_terms"] = source_terms
    return record


def _sentence_checks(target_text: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    for index, sentence in enumerate(_sentences(target_text), start=1):
        terms = _top_terms(sentence, limit=20)
        if not terms:
            continue
        matches = [_sentence_source_match(terms, source) for source in sources if source.get("text_available")]
        matches = sorted(matches, key=lambda item: item["overlap_score"], reverse=True)
        best = matches[0] if matches else None
        best_score = float(best["overlap_score"]) if best else 0.0
        if best_score >= 0.35 and len(best.get("matched_terms", [])) >= 3:
            status = "strong"
        elif best_score > 0:
            status = "weak"
        else:
            status = "unsupported"
        checks.append(
            {
                "sentence_index": index,
                "text": sentence,
                "terms": terms,
                "support_status": status,
                "best_source_id": best.get("source_id") if best else None,
                "best_overlap_score": best_score,
                "matched_terms": best.get("matched_terms", []) if best else [],
                "has_inline_citation": _has_inline_citation(sentence),
            }
        )
    return checks


def _sentence_source_match(terms: list[str], source: dict[str, Any]) -> dict[str, Any]:
    source_terms = set(source.get("source_terms") or [])
    matched_terms = [term for term in terms if term in source_terms]
    return {
        "source_id": source.get("source_id"),
        "overlap_score": round(len(matched_terms) / max(len(terms), 1), 4),
        "matched_terms": matched_terms,
    }


def _sentences(text: str) -> list[str]:
    normalized = " ".join(text.replace("\n", " ").split())
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def _has_inline_citation(sentence: str) -> bool:
    return bool(
        re.search(r"\([A-Z][A-Za-z'-]+(?: et al\.)?,\s*\d{4}[a-z]?\)", sentence)
        or re.search(r"\[[0-9,\s-]+\]", sentence)
    )


def _strengths(comparisons: list[dict[str, Any]], sentence_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    strengths = []
    strong_sources = [
        item
        for item in comparisons
        if item.get("text_available") and float(item.get("overlap_score") or 0) >= 0.25
    ]
    if strong_sources:
        strengths.append(
            {
                "kind": "source_overlap",
                "message": "Accepted or supplied sources share high-signal terms with the target document.",
                "source_ids": [str(item.get("source_id")) for item in strong_sources],
            }
        )
    strong_sentences = [item for item in sentence_checks if item["support_status"] == "strong"]
    if strong_sentences:
        strengths.append(
            {
                "kind": "sentence_overlap",
                "message": "Some target sentences have deterministic overlap with available source text.",
                "sentence_indexes": [item["sentence_index"] for item in strong_sentences],
            }
        )
    if not strengths:
        strengths.append(
            {
                "kind": "no_deterministic_strengths",
                "message": "No deterministic strengths were found from term overlap alone.",
            }
        )
    return strengths


def _weaknesses(comparisons: list[dict[str, Any]], sentence_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weaknesses = []
    missing_text = [item for item in comparisons if not item.get("text_available")]
    if missing_text:
        weaknesses.append(
            {
                "kind": "source_text_missing",
                "message": "Some sources could not be compared because deterministic text was unavailable.",
                "source_ids": [str(item.get("source_id")) for item in missing_text],
            }
        )
    unsupported = [item for item in sentence_checks if item["support_status"] == "unsupported"]
    if unsupported:
        weaknesses.append(
            {
                "kind": "unsupported_sentence_terms",
                "message": "Some target sentences had no deterministic term overlap with available source text.",
                "sentence_indexes": [item["sentence_index"] for item in unsupported],
            }
        )
    weak = [item for item in sentence_checks if item["support_status"] == "weak"]
    if weak:
        weaknesses.append(
            {
                "kind": "weak_sentence_terms",
                "message": "Some target sentences had only weak deterministic overlap with available source text.",
                "sentence_indexes": [item["sentence_index"] for item in weak],
            }
        )
    return weaknesses


def _possible_contradictions() -> list[dict[str, Any]]:
    return [
        {
            "kind": "not_assessed",
            "message": "Deterministic term overlap does not assess contradictions. Human or explicit AI review is required.",
        }
    ]


def _missing_citations(sentence_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sentence_index": item["sentence_index"],
            "text": item["text"],
            "best_source_id": item["best_source_id"],
            "support_status": item["support_status"],
        }
        for item in sentence_checks
        if item["support_status"] in {"strong", "weak"} and not item["has_inline_citation"]
    ]


def _candidate_supporting_sources(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        {
            "source_id": item.get("source_id"),
            "source_kind": item.get("source_kind"),
            "status": item.get("status"),
            "title": item.get("title"),
            "overlap_score": item.get("overlap_score"),
            "matched_terms": item.get("matched_terms"),
        }
        for item in comparisons
        if item.get("text_available") and float(item.get("overlap_score") or 0) > 0
    ]
    return sorted(candidates, key=lambda item: float(item.get("overlap_score") or 0), reverse=True)


def _evidence_confidence(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    confidence_rows = []
    for item in comparisons:
        row = {
            "source_id": item.get("source_id"),
            "claim_relevance": _claim_relevance(item),
            "source_credibility": _source_credibility(item),
            "metadata_completeness": _metadata_completeness(item),
            "recency": _recency(item),
            "citation_strength": _citation_strength(item),
            "author_signals": _author_signals(item),
            "publication_venue_signals": _publication_venue_signals(item),
            "paper_type": _paper_type_signal(item),
            "contradiction_risk": {
                "value": "not_assessed",
                "reason": "Deterministic term overlap does not assess contradiction.",
            },
            "accepted_vs_candidate_status": _accepted_vs_candidate_status(item),
        }
        row["confidence_score"] = _confidence_score(row)
        confidence_rows.append(row)
    return confidence_rows


def _references(comparisons: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    accepted = []
    candidates = []
    for source in comparisons:
        row = {
            "source_id": source.get("source_id"),
            "status": source.get("status"),
            "reference": apa7_reference(
                {
                    "authors": source.get("authors"),
                    "year": source.get("year"),
                    "title": source.get("title"),
                    "publication_venue": source.get("publication_venue"),
                    "doi": source.get("doi"),
                }
            ),
        }
        if source.get("status") == "accepted":
            accepted.append(row)
        else:
            candidates.append(row)
    return {"accepted_workspace_evidence": accepted, "candidate_or_explicit_sources": candidates}


def _claim_relevance(source: dict[str, Any]) -> dict[str, Any]:
    score = float(source.get("overlap_score") or 0)
    if not source.get("text_available"):
        value = "unknown"
    elif score >= 0.25:
        value = "high"
    elif score > 0:
        value = "partial"
    else:
        value = "none_detected"
    return {"value": value, "basis": "deterministic_target_term_overlap", "overlap_score": score}


def _source_credibility(source: dict[str, Any]) -> dict[str, str]:
    if source.get("status") == "accepted" and source.get("source_kind") == "workspace_source":
        return {"value": "accepted_workspace_source", "basis": "workspace_review_status"}
    if source.get("source_kind") == "explicit_path":
        return {"value": "user_supplied_unreviewed_source", "basis": "explicit_source_path"}
    return {"value": "unknown", "basis": "no_review_status_available"}


def _metadata_completeness(source: dict[str, Any]) -> dict[str, Any]:
    fields = ["title", "authors", "year", "doi", "publication_venue", "paper_type"]
    known = [field for field in fields if source.get(field) not in (None, "", "Unknown")]
    return {
        "value": "complete" if len(known) == len(fields) else "partial" if known else "unknown",
        "known_fields": known,
        "unknown_fields": [field for field in fields if field not in known],
    }


def _recency(source: dict[str, Any]) -> dict[str, Any]:
    year = _year_value(source.get("year"))
    if year is None:
        return {"value": "unknown", "year": "Unknown"}
    if year >= 2021:
        value = "recent"
    elif year >= 2011:
        value = "established"
    else:
        value = "older"
    return {"value": value, "year": year}


def _citation_strength(source: dict[str, Any]) -> dict[str, Any]:
    citation_count = _integer_value(source.get("citation_count"))
    if citation_count is None:
        return {"value": "unknown", "citation_count": "Unknown"}
    if citation_count >= 100:
        value = "high"
    elif citation_count >= 10:
        value = "moderate"
    else:
        value = "low"
    return {"value": value, "citation_count": citation_count}


def _author_signals(source: dict[str, Any]) -> dict[str, Any]:
    authors = source.get("authors")
    if authors in (None, "", "Unknown"):
        return {"value": "unknown", "basis": "author metadata unavailable"}
    return {"value": "authors_present", "basis": "author metadata present"}


def _publication_venue_signals(source: dict[str, Any]) -> dict[str, Any]:
    venue = source.get("publication_venue")
    if venue in (None, "", "Unknown"):
        return {"value": "unknown", "basis": "venue metadata unavailable"}
    return {"value": "venue_present", "basis": "venue metadata present", "venue": venue}


def _paper_type_signal(source: dict[str, Any]) -> dict[str, Any]:
    paper_type = source.get("paper_type")
    if paper_type in (None, "", "Unknown"):
        return {"value": "unknown", "paper_type": "Unknown"}
    return {"value": "known", "paper_type": paper_type}


def _accepted_vs_candidate_status(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("status") == "accepted":
        return {"value": "accepted_workspace_evidence", "status": "accepted"}
    if source.get("status") == "explicit":
        return {"value": "explicit_source_not_in_workspace_register", "status": "explicit"}
    return {"value": "unknown", "status": source.get("status") or "Unknown"}


def _confidence_score(confidence: dict[str, Any]) -> dict[str, Any]:
    components = {
        "claim_relevance": _component_score(confidence["claim_relevance"]["value"], {"high": 30, "partial": 15, "none_detected": 0}),
        "source_credibility": _component_score(
            confidence["source_credibility"]["value"],
            {"accepted_workspace_source": 20, "user_supplied_unreviewed_source": 8},
        ),
        "metadata_completeness": _component_score(
            confidence["metadata_completeness"]["value"],
            {"complete": 15, "partial": 8},
        ),
        "recency": _component_score(confidence["recency"]["value"], {"recent": 10, "established": 7, "older": 3}),
        "citation_strength": _component_score(confidence["citation_strength"]["value"], {"high": 10, "moderate": 7, "low": 3}),
        "author_signals": _component_score(confidence["author_signals"]["value"], {"authors_present": 5}),
        "publication_venue_signals": _component_score(confidence["publication_venue_signals"]["value"], {"venue_present": 5}),
        "paper_type": _component_score(confidence["paper_type"]["value"], {"known": 5}),
    }
    known_components = {key: value for key, value in components.items() if value["score"] is not None}
    unknown_components = [key for key, value in components.items() if value["score"] is None]
    score = sum(int(value["score"]) for value in known_components.values())
    return {
        "score": score,
        "scale": "0-100",
        "basis": "deterministic_component_score",
        "components": components,
        "known_component_count": len(known_components),
        "unknown_component_count": len(unknown_components),
        "unknown_components": unknown_components,
        "notes": [
            "Unknown components are not invented.",
            "This score is a deterministic triage signal, not proof of claim support or source quality.",
        ],
    }


def _component_score(value: str, scores: dict[str, int]) -> dict[str, Any]:
    if value == "unknown":
        return {"value": value, "score": None}
    return {"value": value, "score": scores.get(value, 0)}


def _year_value(value: Any) -> int | None:
    match = re.search(r"\b(18|19|20)\d{2}\b", str(value or ""))
    return int(match.group(0)) if match else None


def _integer_value(value: Any) -> int | None:
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _human_review_checklist() -> list[str]:
    return [
        "Review unsupported and weakly supported sentences before relying on this report.",
        "Confirm whether matched terms actually support each claim in context.",
        "Check possible contradictions manually; deterministic validation does not assess contradiction.",
        "Add or correct inline citations where citation gaps are listed.",
        "Verify that all source metadata marked Unknown is completed only from reliable records.",
    ]


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
        "## Guidelines",
        "",
    ]
    if report["guidelines"]:
        lines.extend(
            [
                "| Precedence | Guideline ID | Title | Selection | Scopes |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for guideline in report["guidelines"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(guideline.get("precedence") or "Unknown"),
                        str(guideline.get("id") or "Unknown"),
                        _escape_table(str(guideline.get("title") or "Unknown")),
                        str(guideline.get("selection_source") or "Unknown"),
                        ", ".join(guideline.get("scopes") or []) or "Unknown",
                    ]
                )
                + " |"
            )
    else:
        lines.append("- No default or explicit validation guidelines were applied.")
    lines.extend(
        [
            "",
        "## Strengths",
        "",
        ]
    )
    for strength in report["strengths"]:
        lines.append(f"- {strength['message']}")
    lines.extend(
        [
            "",
            "## Weaknesses",
            "",
        ]
    )
    if report["weaknesses"]:
        for weakness in report["weaknesses"]:
            lines.append(f"- {weakness['message']}")
    else:
        lines.append("- No deterministic weaknesses were found from term overlap alone.")
    lines.extend(
        [
            "",
            "## Unsupported Claims",
            "",
        ]
    )
    if report["unsupported_claims"]:
        for item in report["unsupported_claims"]:
            lines.append(f"- Sentence {item['sentence_index']}: {item['text']}")
    else:
        lines.append("- None detected by deterministic term overlap.")
    lines.extend(
        [
            "",
            "## Weakly Supported Claims",
            "",
        ]
    )
    if report["weakly_supported_claims"]:
        for item in report["weakly_supported_claims"]:
            lines.append(
                f"- Sentence {item['sentence_index']}: best source {item['best_source_id'] or 'Unknown'} "
                f"(score {item['best_overlap_score']})"
            )
    else:
        lines.append("- None detected by deterministic term overlap.")
    lines.extend(
        [
            "",
            "## Possible Contradictions",
            "",
        ]
    )
    for item in report["possible_contradictions"]:
        lines.append(f"- {item['message']}")
    lines.extend(
        [
            "",
            "## Missing Citations",
            "",
        ]
    )
    if report["missing_citations"]:
        for item in report["missing_citations"]:
            lines.append(
                f"- Sentence {item['sentence_index']}: add or verify citation for "
                f"{item['best_source_id'] or 'matched source'}."
            )
    else:
        lines.append("- None detected by simple citation-pattern checks.")
    lines.extend(
        [
            "",
            "## Candidate Supporting Sources",
            "",
            "| Source ID | Status | Title | Overlap score | Matched terms |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for source in report["candidate_supporting_sources"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(source.get("source_id") or "Unknown"),
                    str(source.get("status") or "Unknown"),
                    _escape_table(str(source.get("title") or "Unknown")),
                    str(source.get("overlap_score") or 0),
                    ", ".join(source.get("matched_terms") or []) or "None",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Evidence Confidence Factors",
            "",
            "| Source ID | Score | Unknown components | Claim relevance | Source credibility | Metadata | Recency | Citation strength | Venue | Contradiction risk | Status |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for confidence in report["evidence_confidence"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(confidence.get("source_id") or "Unknown"),
                    str(confidence["confidence_score"]["score"]),
                    str(confidence["confidence_score"]["unknown_component_count"]),
                    str(confidence["claim_relevance"]["value"]),
                    str(confidence["source_credibility"]["value"]),
                    str(confidence["metadata_completeness"]["value"]),
                    str(confidence["recency"]["value"]),
                    str(confidence["citation_strength"]["value"]),
                    str(confidence["publication_venue_signals"]["value"]),
                    str(confidence["contradiction_risk"]["value"]),
                    str(confidence["accepted_vs_candidate_status"]["value"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## References",
            "",
            "### Accepted Workspace Evidence",
            "",
        ]
    )
    accepted_references = report["references"]["accepted_workspace_evidence"]
    if accepted_references:
        for reference in accepted_references:
            lines.append(f"- {reference['reference']}")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "### Candidate Or Explicit Sources",
            "",
        ]
    )
    candidate_references = report["references"]["candidate_or_explicit_sources"]
    if candidate_references:
        for reference in candidate_references:
            lines.append(f"- {reference['reference']}")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Human Review Checklist",
            "",
        ]
    )
    for item in report["human_review_checklist"]:
        lines.append(f"- [ ] {item}")
    lines.extend(
        [
            "",
        "## Source Matches",
        "",
        "| Source ID | Provider | Title | Text available | Overlap score | Matched terms |",
        "| --- | --- | --- | --- | --- | --- |",
        ]
    )
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
