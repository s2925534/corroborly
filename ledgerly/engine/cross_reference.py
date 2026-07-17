from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request

from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.ai import (
    OpenAiCredentials,
    build_safe_context,
    citation_instruction,
    default_openai_model,
    extract_response_text,
    openai_post,
    record_ai_usage,
)
from ledgerly.engine.artefacts import list_artefacts
from ledgerly.engine.claims import list_claims
from ledgerly.engine.grounding import validate_grounding
from ledgerly.engine.sources import list_sources
from ledgerly.engine.vault import add_cross_references_to_upload, list_uploaded_artefacts


WORD_RE = re.compile(r"[A-Za-z0-9]+")
STOP_WORDS = {
    "the", "a", "an", "of", "and", "or", "for", "in", "on", "to", "with",
    "report", "notes", "note", "draft", "final", "copy", "new", "old", "untitled",
}
MIN_TITLE_OR_FILENAME_OVERLAP = 1
MIN_CLAIM_TEXT_OVERLAP = 2
CANDIDATE_REVIEW_STATUSES = {"needs_human_review", "accepted", "approved", "rejected"}


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


_CANDIDATE_BLOCK_RE = re.compile(
    r"###\s*CANDIDATE\s+target_kind=(?P<target_kind>\S+)\s+target_id=(?P<target_id>\S+)\s*\n"
    r"RATIONALE:\s*(?P<rationale>.*?)\s*\n"
    r"###\s*END CANDIDATE",
    re.DOTALL,
)


def _valid_targets(workspace: Path) -> dict[str, dict[str, str]]:
    """`{target_kind: {target_id: target_title}}` for every real artefact,
    source, and claim in the workspace -- the ground truth
    `ai_cross_reference_suggestions` validates every AI-proposed candidate
    against, so a model can never silently invent a target that doesn't
    exist.
    """
    targets: dict[str, dict[str, str]] = {"artefact": {}, "source": {}, "claim": {}}
    for artefact in list_artefacts(workspace):
        if artefact.get("id"):
            targets["artefact"][str(artefact["id"])] = str(artefact.get("title") or artefact["id"])
    for source in list_sources(workspace):
        if source.get("source_id"):
            metadata = source.get("citation_metadata") if isinstance(source.get("citation_metadata"), dict) else {}
            title = source.get("zotero_title") or metadata.get("title") or source.get("file_name") or source["source_id"]
            targets["source"][str(source["source_id"])] = str(title)
    for claim in list_claims(workspace):
        if claim.get("id"):
            targets["claim"][str(claim["id"])] = str(claim.get("text") or claim["id"])[:120]
    return targets


def ai_cross_reference_suggestions(
    workspace: Path,
    credentials: OpenAiCredentials,
    upload_id: str,
    *,
    max_sources: int = 10,
    max_excerpt_chars: int = 1200,
    opener: Callable[[Request], Any] | None = None,
) -> dict[str, Any]:
    """Add AI-suggested cross-reference candidates to the same report
    `cross_reference_candidates` writes, from safe context only (accepted-
    source excerpts, artefact titles, and claim text -- never the uploaded
    file's own content, which isn't converted/extracted by this feature at
    all). Every suggestion is validated against the real workspace (an
    invented `target_id` is dropped, not silently trusted) and the whole
    response is grounding-checked. Additive only: existing deterministic
    keyword-overlap candidates are kept untouched; AI candidates are
    appended with `match_basis: "ai_suggested"` and their own
    `review_status: needs_human_review` -- nothing is ever written or
    applied automatically, the same propose-then-apply boundary
    `apply_cross_reference_links` already enforces for the deterministic
    candidates.
    """
    upload = _find_upload(workspace, upload_id)
    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload_id}.yaml"
    report = read_yaml(report_path) if report_path.is_file() else cross_reference_candidates(workspace, upload_id)
    existing_candidates = [item for item in report.get("candidates", []) if isinstance(item, dict)]

    context = build_safe_context(workspace, max_sources=max_sources, max_excerpt_chars=max_excerpt_chars)
    valid_targets = _valid_targets(workspace)
    claims = list_claims(workspace)
    artefacts = [{"id": a.get("id"), "title": a.get("title")} for a in list_artefacts(workspace) if a.get("id")]

    if not context["has_evidence"] and not claims and not artefacts:
        empty_report = dict(report)
        empty_report["ai_used"] = False
        empty_report["insufficient_evidence"] = True
        empty_report["insufficient_evidence_reason"] = (
            "No accepted source excerpt, claim, or artefact exists in this workspace -- nothing to ground an "
            "AI cross-reference suggestion in."
        )
        empty_report["grounding"] = None
        write_yaml(report_path, empty_report)
        return record_ai_usage(workspace, {**empty_report, "kind": "ai_cross_reference_suggestions"})

    model = default_openai_model(workspace)
    prompt = (
        "You are suggesting cross-reference links for one uploaded artefact in a local-first, evidence-first "
        "research workspace. Given the upload's title/filename and the safe context below (accepted source "
        "excerpts, existing artefact titles, and claim text), propose candidate links to existing artefacts, "
        "sources, or claims that appear genuinely related. Use exactly this format, one block per candidate:\n\n"
        "### CANDIDATE target_kind=<artefact|source|claim> target_id=<id>\n"
        "RATIONALE: <why this link is plausible>\n"
        "### END CANDIDATE\n\n"
        "Only use target_id values that appear in the target map below -- never invent one. If nothing is "
        "genuinely related, propose no candidates at all.\n\n"
        f"{citation_instruction()}\n\n"
        f"Upload: {upload.get('title') or upload.get('original_file_name')}\n\n"
        f"Target map JSON:\n{json.dumps(valid_targets, ensure_ascii=False, indent=2)}\n\n"
        f"Claim ledger JSON:\n{json.dumps(claims, ensure_ascii=False, indent=2)}\n\n"
        f"Safe context JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    response = openai_post("responses", credentials, {"model": model, "input": prompt}, opener=opener)
    text = extract_response_text(response)

    ai_candidates = []
    for match in _CANDIDATE_BLOCK_RE.finditer(text or ""):
        target_kind = match.group("target_kind").strip()
        target_id = match.group("target_id").strip()
        rationale = match.group("rationale").strip()
        if target_id not in valid_targets.get(target_kind, {}):
            continue  # never trust an invented or mismatched-kind target
        ai_candidates.append(
            {
                "target_kind": target_kind,
                "target_id": target_id,
                "target_title": valid_targets[target_kind][target_id],
                "matched_keywords": [],
                "match_basis": "ai_suggested",
                "rationale": rationale,
                "review_status": "needs_human_review",
            }
        )

    merged_candidates = existing_candidates + ai_candidates
    report["candidates"] = merged_candidates
    report["candidate_count"] = len(merged_candidates)
    report["ai_used"] = True
    report["ai_candidate_count"] = len(ai_candidates)
    report["model"] = model
    report["response_id"] = response.get("id") if isinstance(response, dict) else None
    report["grounding"] = validate_grounding(text, context=context, claims=claims)
    write_yaml(report_path, report)
    return record_ai_usage(workspace, {**report, "kind": "ai_cross_reference_suggestions"})


def set_cross_reference_candidate_review_status(
    workspace: Path, upload_id: str, target_kind: str, target_id: str, review_status: str
) -> dict[str, Any]:
    """Set a single candidate's review_status in the persisted candidates report.

    Exists because `apply_cross_reference_links` was designed around a human
    hand-editing the YAML report on disk (fine for CLI/filesystem access),
    which a browser-based reviewer has no way to do — a web UI needs an API
    call that produces the same effect. Only touches the one candidate
    matched by (target_kind, target_id); every other candidate in the report
    is left untouched, so reviewing candidates one at a time never clobbers
    a sibling candidate's already-recorded decision.
    """
    if review_status not in CANDIDATE_REVIEW_STATUSES:
        allowed = ", ".join(sorted(CANDIDATE_REVIEW_STATUSES))
        raise ValueError(f"Invalid review_status '{review_status}'. Must be one of: {allowed}")

    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload_id}.yaml"
    if not report_path.is_file():
        raise ValueError(f"No cross-reference candidates found for {upload_id}. Run cross_reference_candidates first.")

    report = read_yaml(report_path)
    candidates = [item for item in report.get("candidates", []) if isinstance(item, dict)]
    for candidate in candidates:
        if candidate.get("target_kind") == target_kind and candidate.get("target_id") == target_id:
            candidate["review_status"] = review_status
            report["candidates"] = candidates
            write_yaml(report_path, report)
            return candidate

    raise ValueError(f"No candidate found for upload_id={upload_id} with target_kind={target_kind}, target_id={target_id}")


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
