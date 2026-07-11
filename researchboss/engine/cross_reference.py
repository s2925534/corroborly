from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.artefacts import list_artefacts
from researchboss.engine.claims import list_claims
from researchboss.engine.sources import list_sources
from researchboss.engine.vault import add_cross_references_to_upload, list_uploaded_artefacts


WORD_RE = re.compile(r"[A-Za-z0-9]+")
STOP_WORDS = {
    "the", "a", "an", "of", "and", "or", "for", "in", "on", "to", "with",
    "report", "notes", "note", "draft", "final", "copy", "new", "old", "untitled",
}
MIN_TITLE_OR_FILENAME_OVERLAP = 1
MIN_CLAIM_TEXT_OVERLAP = 2


def cross_reference_candidates(workspace: Path, upload_id: str) -> dict[str, Any]:
    """Propose deterministic links between an uploaded artefact and existing workspace items.

    Matches by shared keyword tokens between the upload's title/filename and
    each candidate's title/filename/text — filename or title overlap, source
    metadata title overlap, and claim text overlap. This is a proposal step
    only: nothing is written into any artefact, source, or claim record, and
    no links are applied. Each candidate starts with
    `review_status: needs_human_review`; edit the persisted report file to
    "accepted" or "approved" per candidate before calling
    `apply_cross_reference_links`, mirroring how citation plans work.
    """
    upload = _find_upload(workspace, upload_id)
    upload_tokens = _tokenize(str(upload.get("title") or "")) | _tokenize(str(upload.get("original_file_name") or ""))

    candidates: list[dict[str, Any]] = []
    candidates.extend(_artefact_candidates(workspace, upload_tokens))
    candidates.extend(_source_candidates(workspace, upload_tokens))
    candidates.extend(_claim_candidates(workspace, upload_tokens))

    report = {
        "version": 1,
        "upload_id": upload_id,
        "upload_title": upload.get("title"),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "links_written": False,
        "notes": "Deterministic keyword-overlap candidates only. Review before treating any candidate as confirmed.",
    }
    write_yaml(workspace / "outputs" / "recommendations" / f"cross-reference-{upload_id}.yaml", report)
    return report


def _find_upload(workspace: Path, upload_id: str) -> dict[str, Any]:
    for record in list_uploaded_artefacts(workspace):
        if record.get("upload_id") == upload_id:
            return record
    raise ValueError(f"Unknown upload_id: {upload_id}")


def _tokenize(text: str) -> set[str]:
    return {word.lower() for word in WORD_RE.findall(text) if len(word) > 2 and word.lower() not in STOP_WORDS}


def _artefact_candidates(workspace: Path, upload_tokens: set[str]) -> list[dict[str, Any]]:
    rows = []
    for artefact in list_artefacts(workspace):
        title = str(artefact.get("title") or "")
        file_name = Path(str(artefact.get("path") or "")).name
        overlap = upload_tokens & (_tokenize(title) | _tokenize(file_name))
        if len(overlap) < MIN_TITLE_OR_FILENAME_OVERLAP:
            continue
        rows.append(
            {
                "target_kind": "artefact",
                "target_id": artefact.get("id"),
                "target_title": title or file_name,
                "matched_keywords": sorted(overlap),
                "match_basis": "title_or_filename_keyword_overlap",
                "review_status": "needs_human_review",
            }
        )
    return rows


def _source_candidates(workspace: Path, upload_tokens: set[str]) -> list[dict[str, Any]]:
    rows = []
    for source in list_sources(workspace):
        metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
        title = str(source.get("zotero_title") or metadata.get("title") or "")
        file_name = str(source.get("file_name") or "")
        overlap = upload_tokens & (_tokenize(title) | _tokenize(file_name))
        if len(overlap) < MIN_TITLE_OR_FILENAME_OVERLAP:
            continue
        rows.append(
            {
                "target_kind": "source",
                "target_id": source.get("source_id"),
                "target_title": title or file_name,
                "matched_keywords": sorted(overlap),
                "match_basis": "title_or_filename_keyword_overlap",
                "review_status": "needs_human_review",
            }
        )
    return rows


def _claim_candidates(workspace: Path, upload_tokens: set[str]) -> list[dict[str, Any]]:
    rows = []
    for claim in list_claims(workspace):
        text = str(claim.get("text") or "")
        overlap = upload_tokens & _tokenize(text)
        if len(overlap) < MIN_CLAIM_TEXT_OVERLAP:  # claim text is long/generic; require a stronger signal
            continue
        rows.append(
            {
                "target_kind": "claim",
                "target_id": claim.get("id"),
                "target_title": text[:120],
                "matched_keywords": sorted(overlap),
                "match_basis": "claim_text_keyword_overlap",
                "review_status": "needs_human_review",
            }
        )
    return rows


def apply_cross_reference_links(workspace: Path, upload_id: str) -> dict[str, Any]:
    """Write reviewed cross-reference links as metadata on the upload record.

    Reads the candidate report `cross_reference_candidates` already wrote
    (`outputs/recommendations/cross-reference-<upload_id>.yaml`) and applies
    only the candidates whose `review_status` has been hand-edited to
    "accepted" or "approved" — the same review-before-apply convention
    citation plans use (`create_citation_plan` writes a plan file with
    `review_status: needs_human_review` per insertion; `apply_citation_plan`
    only applies the ones a human has since marked accepted).

    Links are recorded as metadata on the upload record only, via
    `vault.add_cross_references_to_upload` — mirroring how artefact records
    already track `linked_sources`/`linked_research_questions` as metadata.
    No artefact, source, or claim document's content is ever modified. This
    was a deliberate choice over literal document-content insertion (the
    other reading of "write the link" the TODO/CONTRACT left open): content
    insertion would need the same per-format `.md`/`.docx`/`.pdf` handling
    `citations.apply_citation_plan` already has, for a much less certain
    payoff — a keyword-overlap cross-reference is weaker evidence than a
    validated missing-citation match, so inserting text automatically on
    that basis is a worse default than recording it as reviewable metadata.
    """
    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload_id}.yaml"
    if not report_path.is_file():
        raise ValueError(f"No cross-reference candidates found for {upload_id}. Run cross_reference_candidates first.")

    report = read_yaml(report_path)
    candidates = [item for item in report.get("candidates", []) if isinstance(item, dict)]
    approved = [item for item in candidates if str(item.get("review_status") or "").lower() in {"accepted", "approved"}]

    links = [
        {
            "target_kind": item.get("target_kind"),
            "target_id": item.get("target_id"),
            "target_title": item.get("target_title"),
            "matched_keywords": item.get("matched_keywords"),
        }
        for item in approved
    ]
    updated_upload = add_cross_references_to_upload(workspace, upload_id, links)

    report["links_written"] = True
    report["applied_count"] = len(links)
    write_yaml(report_path, report)

    return {
        "version": 1,
        "upload_id": upload_id,
        "applied_count": len(links),
        "skipped_count": len(candidates) - len(approved),
        "cross_references": updated_upload.get("cross_references", []),
    }
