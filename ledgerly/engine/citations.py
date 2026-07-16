from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.conversion import extract_text
from ledgerly.engine.doc_validation import validate_document
from ledgerly.engine.document_targets import resolve_document_target
from ledgerly.engine.references import CITATION_STYLES, format_inline_citation, format_reference
from ledgerly.engine.vault import create_document_version


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD = f"{{{WORD_NAMESPACE}}}"
CITATION_INSERTION_REVIEW_STATUSES = {"needs_human_review", "accepted", "approved", "rejected"}


@dataclass(frozen=True)
class CitationPlanRun:
    plan: dict[str, Any]
    yaml_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class CitationApplyRun:
    applied: int
    skipped: int
    output_path: Path
    report_path: Path
    version_id: str
    source_snapshot_version_id: str


def create_citation_plan(
    workspace: Path,
    target: str,
    *,
    source_paths: list[Path] | None = None,
    guideline_ids: list[str] | None = None,
    use_default_guidelines: bool = True,
    allow_candidate_citations: bool = False,
    citation_style: str = "apa7",
    cwd: Path | None = None,
) -> CitationPlanRun:
    if citation_style not in CITATION_STYLES:
        raise ValueError(
            f"Unknown citation style: {citation_style}. Expected one of: {', '.join(sorted(CITATION_STYLES))}"
        )
    validation = validate_document(
        workspace,
        target,
        source_paths=source_paths,
        guideline_ids=guideline_ids,
        use_default_guidelines=use_default_guidelines,
        cwd=cwd,
    )
    report = validation.report
    source_map = {str(source.get("source_id")): source for source in report.get("sources", [])}
    confidence_map = {
        str(item.get("source_id")): item.get("confidence_score", {})
        for item in report.get("evidence_confidence", [])
    }
    references = report.get("references", {})
    number_map = (
        _assign_citation_numbers(report.get("missing_citations", []), references)
        if citation_style == "ieee"
        else {}
    )
    insertions = []
    blocked_candidate_citations = []
    for item in report.get("missing_citations", []):
        source_id = item.get("best_source_id")
        source = source_map.get(str(source_id))
        if not source:
            continue
        if source.get("status") != "accepted" and not allow_candidate_citations:
            blocked_candidate_citations.append(
                {
                    "sentence_index": item.get("sentence_index"),
                    "target_sentence": item.get("text"),
                    "source_id": source_id,
                    "source_status": source.get("status"),
                    "reason": "candidate_citations_require_explicit_allow_flag",
                }
            )
            continue
        insertions.append(
            {
                "sentence_index": item.get("sentence_index"),
                "target_sentence": item.get("text"),
                "source_id": source_id,
                "suggested_inline_citation": format_inline_citation(
                    source, citation_style, number=number_map.get(str(source_id))
                ),
                "citation_position": "end_of_sentence_before_final_punctuation",
                "support_status": item.get("support_status"),
                "confidence_score": confidence_map.get(str(source_id), {}).get("score"),
                "review_status": "needs_human_review",
            }
        )

    plan = {
        "version": 1,
        "target": report["target"],
        "validation_report": str(validation.yaml_path),
        "ai_used": False,
        "original_document_modified": False,
        "plan_status": "review_required",
        "allow_candidate_citations": allow_candidate_citations,
        "citation_style": citation_style,
        "insertions": insertions,
        "blocked_candidate_citations": blocked_candidate_citations,
        "references": _styled_references(references, citation_style, number_map),
        "guidelines": report.get("guidelines", []),
        "limitations": [
            "This is a deterministic citation insertion plan only.",
            "It does not edit the original document.",
            "Human review is required before applying any citation.",
        ]
        + (
            ["Non-APA reference formatting is a simplified approximation -- verify against your institution's exact style guide before submission."]
            if citation_style != "apa7"
            else []
        ),
    }
    yaml_path = _plan_path(workspace, Path(str(report["target"]["path"])), ".yaml")
    markdown_path = _plan_path(workspace, Path(str(report["target"]["path"])), ".md")
    write_yaml(yaml_path, plan)
    markdown_path.write_text(_markdown_plan(plan), encoding="utf-8")
    return CitationPlanRun(plan=plan, yaml_path=yaml_path, markdown_path=markdown_path)


def set_citation_plan_insertion_review_status(
    workspace: Path,
    target: str,
    sentence_index: int,
    source_id: str,
    review_status: str,
    *,
    plan_path: Path | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Set a single citation-plan insertion's review_status in the persisted plan file.

    `create_citation_plan`/`apply_citation_plan` were designed around a
    human hand-editing the plan YAML on disk — fine for CLI/filesystem
    access, but a browser-based reviewer has no way to do that. This is the
    missing API-reachable equivalent, mirroring
    `cross_reference.set_cross_reference_candidate_review_status`. Only
    touches the one insertion matched by (sentence_index, source_id) —
    the same pair `create_citation_plan` builds each insertion from — so
    reviewing one insertion never clobbers a sibling insertion's already-
    recorded decision.
    """
    if review_status not in CITATION_INSERTION_REVIEW_STATUSES:
        allowed = ", ".join(sorted(CITATION_INSERTION_REVIEW_STATUSES))
        raise ValueError(f"Invalid review_status '{review_status}'. Must be one of: {allowed}")

    resolved_target = resolve_document_target(workspace, target, cwd=cwd)
    plan_yaml = plan_path or _plan_path(workspace, resolved_target.path, ".yaml")
    if not plan_yaml.exists():
        raise ValueError(f"Citation plan does not exist: {plan_yaml}")

    plan = read_yaml(plan_yaml)
    insertions = [item for item in plan.get("insertions", []) if isinstance(item, dict)]
    for insertion in insertions:
        if insertion.get("sentence_index") == sentence_index and str(insertion.get("source_id")) == str(source_id):
            insertion["review_status"] = review_status
            plan["insertions"] = insertions
            write_yaml(plan_yaml, plan)
            return insertion

    raise ValueError(f"No insertion found for sentence_index={sentence_index}, source_id={source_id}")


def apply_citation_plan(
    workspace: Path,
    target: str,
    *,
    plan_path: Path | None = None,
    cwd: Path | None = None,
) -> CitationApplyRun:
    resolved_target = resolve_document_target(workspace, target, cwd=cwd)
    target_suffix = resolved_target.path.suffix.lower()
    if target_suffix not in {".md", ".txt", ".docx", ".pdf"}:
        raise ValueError(
            "Deterministic citation plan application currently supports Markdown, TXT, DOCX, and PDF-to-Markdown targets."
        )

    plan_yaml = plan_path or _plan_path(workspace, resolved_target.path, ".yaml")
    if not plan_yaml.exists():
        raise ValueError(f"Citation plan does not exist: {plan_yaml}")
    plan = read_yaml(plan_yaml)
    insertions = [item for item in plan.get("insertions", []) if isinstance(item, dict)]
    approved = [
        item
        for item in insertions
        if str(item.get("review_status") or "").lower() in {"accepted", "approved"}
    ]

    if target_suffix == ".docx":
        output_path = _applied_path(workspace, resolved_target.path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        applied = _apply_to_docx(resolved_target.path, output_path, approved, plan.get("references") or {})
    else:
        if target_suffix == ".pdf":
            text = extract_text(resolved_target.path)
            output_path = _applied_path(workspace, resolved_target.path, suffix=".md")
        else:
            text = resolved_target.path.read_text(encoding="utf-8", errors="replace")
            output_path = _applied_path(workspace, resolved_target.path)
        revised, applied = _apply_to_text(text, approved)
        revised = _append_references(revised, plan.get("references") or {})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(revised, encoding="utf-8")

    validation_report_ref = plan.get("validation_report")
    validation_report_id = Path(str(validation_report_ref)).stem if validation_report_ref else None
    citation_plan_id = plan_yaml.stem

    source_snapshot = create_document_version(
        workspace,
        str(resolved_target.path),
        creation_reason="pre_citation_apply_snapshot",
        source_command="cite apply",
        cwd=cwd,
    )
    applied_version = create_document_version(
        workspace,
        str(output_path),
        creation_reason="citation_apply",
        source_command="cite apply",
        parent_version_id=source_snapshot["version_id"],
        validation_report_id=validation_report_id,
        citation_plan_id=citation_plan_id,
        cwd=cwd,
    )

    report = {
        "version": 1,
        "target": str(resolved_target.path),
        "plan_path": str(plan_yaml),
        "output_path": str(output_path),
        "target_format": target_suffix.lstrip(".") or "unknown",
        "output_format": output_path.suffix.lower().lstrip(".") or "unknown",
        "original_document_modified": False,
        "applied_insertions": applied,
        "skipped_insertions": len(insertions) - applied,
        "document_version_id": applied_version["version_id"],
        "source_snapshot_version_id": source_snapshot["version_id"],
    }
    report_path = _applied_report_path(workspace, resolved_target.path)
    write_yaml(report_path, report)
    return CitationApplyRun(
        applied=applied,
        skipped=len(insertions) - applied,
        output_path=output_path,
        report_path=report_path,
        version_id=applied_version["version_id"],
        source_snapshot_version_id=source_snapshot["version_id"],
    )


def _apply_to_text(text: str, insertions: list[dict[str, Any]]) -> tuple[str, int]:
    revised = text
    applied = 0
    for insertion in insertions:
        sentence = str(insertion.get("target_sentence") or "").strip()
        citation = str(insertion.get("suggested_inline_citation") or "").strip()
        if not sentence or not citation or citation in sentence:
            continue
        revised_sentence = _insert_citation(sentence, citation)
        if sentence in revised:
            revised = revised.replace(sentence, revised_sentence, 1)
            applied += 1
            continue
        pattern = _whitespace_flexible_pattern(sentence)
        match = pattern.search(revised)
        if match and citation not in match.group(0):
            revised = revised[: match.start()] + _insert_citation(match.group(0), citation) + revised[match.end() :]
            applied += 1
    return revised, applied


def _whitespace_flexible_pattern(text: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in text.split()]
    return re.compile(r"\s+".join(parts))


def _apply_to_docx(
    source_path: Path,
    output_path: Path,
    insertions: list[dict[str, Any]],
    references: dict[str, Any],
) -> int:
    with zipfile.ZipFile(source_path) as source_docx:
        document_xml = source_docx.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
        applied = _apply_insertions_to_docx_root(root, insertions)
        _append_docx_references(root, references)
        updated_xml = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as revised_docx:
            for item in source_docx.infolist():
                if item.filename == "word/document.xml":
                    revised_docx.writestr(item, updated_xml)
                else:
                    revised_docx.writestr(item, source_docx.read(item.filename))
    return applied


def _apply_insertions_to_docx_root(root: ElementTree.Element, insertions: list[dict[str, Any]]) -> int:
    applied = 0
    paragraphs = root.findall(f".//{WORD}p")
    for insertion in insertions:
        sentence = str(insertion.get("target_sentence") or "").strip()
        citation = str(insertion.get("suggested_inline_citation") or "").strip()
        if not sentence or not citation:
            continue
        for paragraph in paragraphs:
            paragraph_text = _docx_paragraph_text(paragraph)
            if sentence in paragraph_text and citation not in paragraph_text:
                _replace_docx_paragraph_text(paragraph, paragraph_text.replace(sentence, _insert_citation(sentence, citation), 1))
                applied += 1
                break
    return applied


def _append_docx_references(root: ElementTree.Element, references: dict[str, Any]) -> None:
    accepted = references.get("accepted_workspace_evidence") if isinstance(references, dict) else []
    lines = [str(item.get("reference")) for item in accepted if isinstance(item, dict) and item.get("reference")]
    if not lines:
        return
    body = root.find(f".//{WORD}body")
    if body is None:
        return
    body.append(_docx_paragraph("References"))
    for line in lines:
        body.append(_docx_paragraph(line))


def _docx_paragraph(text: str) -> ElementTree.Element:
    paragraph = ElementTree.Element(f"{WORD}p")
    run = ElementTree.SubElement(paragraph, f"{WORD}r")
    text_node = ElementTree.SubElement(run, f"{WORD}t")
    text_node.text = text
    return paragraph


def _docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    return "".join(text_node.text or "" for text_node in paragraph.findall(f".//{WORD}t"))


def _replace_docx_paragraph_text(paragraph: ElementTree.Element, text: str) -> None:
    text_nodes = paragraph.findall(f".//{WORD}t")
    if not text_nodes:
        run = ElementTree.SubElement(paragraph, f"{WORD}r")
        text_node = ElementTree.SubElement(run, f"{WORD}t")
        text_node.text = text
        return
    text_nodes[0].text = text
    for text_node in text_nodes[1:]:
        text_node.text = ""


def _assign_citation_numbers(
    missing_citations: list[dict[str, Any]], references: dict[str, Any]
) -> dict[str, int]:
    """IEEE-style running numbers, assigned by order of first appearance:
    sources actually cited inline first (in the order sentences reference
    them), then any remaining accepted sources that only appear in the
    reference list. Stable per plan generation, not a global source ID.
    """
    numbers: dict[str, int] = {}
    next_number = 1
    for item in missing_citations:
        source_id = str(item.get("best_source_id"))
        if source_id and source_id not in numbers:
            numbers[source_id] = next_number
            next_number += 1
    accepted = references.get("accepted_workspace_evidence") if isinstance(references, dict) else []
    for row in accepted or []:
        source_id = str(row.get("source_id"))
        if source_id and source_id not in numbers:
            numbers[source_id] = next_number
            next_number += 1
    return numbers


def _styled_references(
    references: dict[str, Any], style: str, number_map: dict[str, int]
) -> dict[str, Any]:
    """Reformat `doc_validation`'s always-APA reference rows into the
    requested citation style, using the raw metadata each row already
    carries (`doc_validation._references`). Left untouched for the default
    `apa7` style, so existing plans/tests see byte-identical output.
    """
    if style == "apa7":
        return references
    styled: dict[str, list[dict[str, Any]]] = {}
    for key in ("accepted_workspace_evidence", "candidate_or_explicit_sources"):
        rows = references.get(key) if isinstance(references, dict) else []
        styled_rows = []
        for row in rows or []:
            metadata = row.get("metadata") if isinstance(row, dict) else None
            if not isinstance(metadata, dict):
                styled_rows.append(row)
                continue
            source_id = str(row.get("source_id"))
            styled_rows.append(
                {**row, "reference": format_reference(metadata, style, number=number_map.get(source_id))}
            )
        styled[key] = styled_rows
    return styled


def _insert_citation(sentence: str, citation: str) -> str:
    stripped = sentence.rstrip()
    if stripped.endswith((".", "!", "?")):
        return f"{stripped[:-1]} {citation}{stripped[-1]}"
    return f"{stripped} {citation}"


def _append_references(text: str, references: dict[str, Any]) -> str:
    accepted = references.get("accepted_workspace_evidence") if isinstance(references, dict) else []
    if not accepted:
        return text
    lines = [str(item.get("reference")) for item in accepted if isinstance(item, dict) and item.get("reference")]
    if not lines:
        return text
    base = text.rstrip()
    return base + "\n\n## References\n\n" + "\n".join(f"- {line}" for line in lines) + "\n"


def _plan_path(workspace: Path, target_path: Path, suffix: str) -> Path:
    stem = "".join(ch.lower() if ch.isalnum() else "-" for ch in target_path.stem).strip("-") or "target"
    return workspace / "outputs" / "citation-plans" / f"citation-plan-{stem}{suffix}"


def _applied_path(workspace: Path, target_path: Path, *, suffix: str | None = None) -> Path:
    stem = "".join(ch.lower() if ch.isalnum() else "-" for ch in target_path.stem).strip("-") or "target"
    output_suffix = suffix or target_path.suffix.lower() or ".md"
    return workspace / "outputs" / "citation-plans" / f"citation-applied-{stem}{output_suffix}"


def _applied_report_path(workspace: Path, target_path: Path) -> Path:
    stem = "".join(ch.lower() if ch.isalnum() else "-" for ch in target_path.stem).strip("-") or "target"
    return workspace / "outputs" / "citation-plans" / f"citation-apply-{stem}.yaml"


def _markdown_plan(plan: dict[str, Any]) -> str:
    lines = [
        f"# Citation Plan: {Path(str(plan['target']['path'])).name}",
        "",
        "- AI used: No",
        "- Original document modified: No",
        "- Plan status: review required",
        f"- Citation style: {plan.get('citation_style', 'apa7')}",
        "",
        "## Proposed Insertions",
        "",
        "| Sentence | Source ID | Suggested citation | Confidence | Review status |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not plan["insertions"]:
        lines.append("| None | None | None | None | None |")
    for insertion in plan["insertions"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(insertion.get("sentence_index") or "Unknown"),
                    str(insertion.get("source_id") or "Unknown"),
                    str(insertion.get("suggested_inline_citation") or "Unknown"),
                    str(insertion.get("confidence_score") or "Unknown"),
                    str(insertion.get("review_status") or "Unknown"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Limitations", ""])
    for limitation in plan["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"
