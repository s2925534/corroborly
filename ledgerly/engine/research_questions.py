from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.progress_log import record_progress_event


# A standard, deterministic research-methods taxonomy — not invented per-answer.
# Each maps to a fixed question stem used to deterministically compose a
# research question from a user's free-text "phenomenon or relationship of
# interest" and "scope/context" answers (see `compose_research_question`).
QUESTION_TYPES = {"descriptive", "comparative", "causal", "evaluative"}
QUESTION_TYPE_STEMS = {
    "descriptive": "What is",
    "comparative": "How does",
    "causal": "To what extent does",
    "evaluative": "How effective is",
}


QUESTION_STARTERS = (
    "how",
    "why",
    "what",
    "which",
    "whether",
    "does",
    "do",
    "can",
    "could",
    "should",
    "to what extent",
    "in what ways",
)
VAGUE_TERMS = {
    "stuff",
    "things",
    "better",
    "good",
    "bad",
    "impact",
    "effective",
    "important",
    "useful",
    "successful",
}
CONTEXT_MARKERS = {"in", "within", "among", "across", "for", "between", "during", "through"}
RELATION_MARKERS = {
    "affect",
    "affects",
    "effect",
    "impact",
    "influence",
    "relationship",
    "compare",
    "comparison",
    "extent",
    "role",
    "contribute",
    "contributes",
}


def _paths(workspace: Path) -> tuple[Path, Path, Path]:
    return (
        workspace / "research-questions.yaml",
        workspace / "research-question-candidates.yaml",
        workspace / "rejected-research-questions.yaml",
    )


def list_research_questions(workspace: Path) -> dict[str, list[dict[str, Any]]]:
    approved_path, candidates_path, rejected_path = _paths(workspace)
    return {
        "approved": list(read_yaml(approved_path).get("research_questions", [])),
        "candidates": list(read_yaml(candidates_path).get("candidates", [])),
        "rejected": list(read_yaml(rejected_path).get("rejected", [])),
    }


def compose_research_question(relation: str, scope: str, question_type: str) -> str:
    """Deterministically assemble a research question from a fixed stem for
    `question_type` plus the user's own "phenomenon or relationship of
    interest" (`relation`) and "scope/context" (`scope`) answers — no AI
    involved, so quality depends on how the user phrases their own answers,
    same as filling in a form. Feed the result through
    `assess_research_question_readiness` for feedback rather than trusting
    it's well-formed by construction.
    """
    if question_type not in QUESTION_TYPES:
        allowed = ", ".join(sorted(QUESTION_TYPES))
        raise ValueError(f"Invalid question_type: {question_type!r}. Expected one of: {allowed}")
    relation = relation.strip().rstrip("?.")
    scope = scope.strip()
    stem = QUESTION_TYPE_STEMS[question_type]
    tail = f" in {scope}" if scope else ""
    return f"{stem} {relation}{tail}?"


def split_candidate_relations(relation_text: str) -> list[str]:
    """Split a "phenomenon or relationship of interest" answer that implies
    more than one distinct angle into separate phrases, so the wizard can
    propose a small set of candidate research questions rather than forcing
    one. Splits on commas, semicolons, and standalone " and "/" or " —
    deliberately simple and deterministic (no AI judgment call about what
    counts as a "distinct angle"), matching how a person would naturally
    list several things in one sentence. Returns a single-item list
    unchanged when there's nothing to split.
    """
    parts = re.split(r"\s*(?:,|;|\band\b|\bor\b)\s*", relation_text.strip())
    parts = [part.strip() for part in parts if part.strip()]
    return parts or [relation_text.strip()]


def _next_rq_id(workspace: Path) -> str:
    groups = list_research_questions(workspace)
    numbers = []
    for items in groups.values():
        for item in items:
            match = re.match(r"^rq-(\d+)$", str(item.get("id", "")))
            if match:
                numbers.append(int(match.group(1)))
    return f"rq-{max(numbers, default=0) + 1:03d}"


def add_research_question_candidate(
    workspace: Path,
    question: str,
    *,
    subquestions: list[str] | None = None,
    hypothesis: str | None = None,
    question_type: str | None = None,
    proof_criteria: str | None = None,
    disproof_criteria: str | None = None,
) -> dict[str, Any]:
    """Add a draft research question outside of `init_workspace` — the only
    way to create one before this function existed. Saved through the same
    candidates file `init_workspace` already writes to, so `rqs
    list/check/assess/approve/reject/archive` work on it identically to an
    init-time or manually-drafted RQ; no new storage mechanism.
    """
    question = question.strip()
    if not question:
        raise ValueError("Research question text is required.")
    if question_type is not None and question_type not in QUESTION_TYPES:
        allowed = ", ".join(sorted(QUESTION_TYPES))
        raise ValueError(f"Invalid question_type: {question_type!r}. Expected one of: {allowed}")

    _, candidates_path, _ = _paths(workspace)
    candidates_doc = read_yaml(candidates_path)
    candidates = list(candidates_doc.get("candidates", []))
    record: dict[str, Any] = {
        "id": _next_rq_id(workspace),
        "question": question,
        "subquestions": list(subquestions or []),
        "status": "draft",
    }
    if hypothesis:
        record["hypothesis"] = hypothesis.strip()
    if question_type:
        record["question_type"] = question_type
    if proof_criteria:
        record["proof_criteria"] = proof_criteria.strip()
    if disproof_criteria:
        record["disproof_criteria"] = disproof_criteria.strip()

    candidates.append(record)
    candidates_doc["version"] = candidates_doc.get("version", 1)
    candidates_doc["candidates"] = candidates
    write_yaml(candidates_path, candidates_doc)
    record_progress_event(workspace, kind="rq_candidate_added", entity_id=record["id"], detail=question)
    return record


def check_research_question_readiness(
    workspace: Path,
    rq_id: str | None = None,
) -> dict[str, Any]:
    """Run deterministic readiness checks over research questions and write a local report."""
    groups = list_research_questions(workspace)
    context = read_yaml(workspace / "research-context.yaml")
    project_type = str(context.get("project", {}).get("type", ""))

    checked: list[dict[str, Any]] = []
    matched = False
    for group, items in groups.items():
        for item in items:
            if rq_id is not None and item.get("id") != rq_id:
                continue
            matched = True
            readiness = assess_research_question_readiness(
                str(item.get("question", "")),
                subquestions=list(item.get("subquestions", [])),
                project_type=project_type,
            )
            checked.append(
                {
                    "id": item.get("id"),
                    "group": group,
                    "question": item.get("question"),
                    "readiness": readiness,
                }
            )
            item["readiness"] = {
                "status": readiness["status"],
                "score": readiness["score"],
                "checked_by": "deterministic_rules",
                "human_review_required": True,
            }

    if rq_id is not None and not matched:
        raise ValueError(f"Unknown research question: {rq_id}")

    _write_research_question_groups(workspace, groups)
    report = {
        "version": 1,
        "method": "deterministic_rules",
        "human_review_required": True,
        "ai_used": False,
        "certainty_note": (
            "This report checks readiness signals only. Novelty, contribution strength, field usefulness, "
            "and evidence quality require human review or later AI-assisted workflows."
        ),
        "checked_count": len(checked),
        "research_questions": checked,
    }
    output_path = workspace / "outputs" / "validation" / "research-question-readiness.yaml"
    write_yaml(output_path, report)
    return report


def assess_research_question_readiness(
    question: str,
    *,
    subquestions: list[Any] | None = None,
    project_type: str = "",
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    clean = " ".join(question.strip().split())
    words = _words(clean)
    lowered = clean.lower()

    def add(code: str, severity: str, message: str) -> None:
        findings.append({"code": code, "severity": severity, "message": message})

    if not clean:
        add("missing_question", "error", "Question text is empty.")
    elif len(words) < 6:
        add("too_short", "warning", "Question is very short and may need more scope/context.")

    if clean and not clean.endswith("?"):
        add("not_question_form", "warning", "Question does not end with a question mark.")

    if clean and not _starts_like_question(lowered):
        add("weak_question_starter", "info", "Question does not start with a common research question opener.")

    if len(words) > 45:
        add("possibly_too_broad", "warning", "Question is long and may contain too much scope for one RQ.")

    if clean.count("?") > 1 or _looks_like_multiple_questions(lowered):
        add("possibly_multiple_questions", "warning", "Question may contain multiple questions.")

    vague = sorted({word for word in words if word in VAGUE_TERMS})
    if vague:
        add("vague_terms", "warning", f"Potentially vague terms found: {', '.join(vague)}.")

    if not (set(words) & CONTEXT_MARKERS):
        add("missing_context_marker", "info", "No simple context marker was detected, such as in/within/among/for.")

    if not (set(words) & RELATION_MARKERS) and not any(lowered.startswith(prefix) for prefix in ("how ", "why ")):
        add("missing_relationship_marker", "info", "No simple relationship, mechanism, comparison, or contribution marker was detected.")

    subquestions = subquestions or []
    if subquestions and not _subquestions_share_terms(words, subquestions):
        add("weak_subquestion_alignment", "warning", "Subquestions share few terms with the main research question.")

    if project_type.lower() == "phd" and not (set(words) & {"contribute", "contributes", "novel", "original", "theory", "method"}):
        add("phd_contribution_not_explicit", "info", "For PhD work, the question may need an explicit contribution, theory, method, or originality signal.")

    if project_type.lower() == "m.phil" and len(words) > 35:
        add("mphil_scope_warning", "warning", "For M.Phil work, the question may need tighter scope for feasibility.")

    score = _readiness_score(findings)
    return {
        "status": _readiness_status(findings),
        "score": score,
        "findings": findings,
        "limits": [
            "Does not validate novelty.",
            "Does not judge contribution strength.",
            "Does not determine field usefulness.",
            "Does not assess evidence quality.",
        ],
        "ai_required_for_higher_certainty": [
            "novelty assessment",
            "contribution strength",
            "field usefulness",
            "evidence-quality reasoning",
        ],
    }


def _find_and_remove(items: list[dict[str, Any]], rq_id: str) -> Optional[dict[str, Any]]:
    for index, item in enumerate(items):
        if item.get("id") == rq_id:
            return items.pop(index)
    return None


def _write_research_question_groups(workspace: Path, groups: dict[str, list[dict[str, Any]]]) -> None:
    approved_path, candidates_path, rejected_path = _paths(workspace)
    write_yaml(approved_path, {"version": 1, "research_questions": groups["approved"]})
    write_yaml(candidates_path, {"version": 1, "candidates": groups["candidates"]})
    write_yaml(rejected_path, {"version": 1, "rejected": groups["rejected"]})


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower())


def _starts_like_question(text: str) -> bool:
    return any(text.startswith(starter + " ") or text == starter for starter in QUESTION_STARTERS)


def _looks_like_multiple_questions(text: str) -> bool:
    return bool(re.search(r"\b(and|or)\s+(how|why|what|which|whether|does|can|could|should)\b", text))


def _subquestions_share_terms(main_words: list[str], subquestions: list[Any]) -> bool:
    main = {word for word in main_words if len(word) > 3}
    sub = {
        word
        for subquestion in subquestions
        for word in _words(str(subquestion))
        if len(word) > 3
    }
    if not main or not sub:
        return False
    return bool(main & sub)


def _readiness_score(findings: list[dict[str, Any]]) -> int:
    score = 100
    for finding in findings:
        if finding["severity"] == "error":
            score -= 35
        elif finding["severity"] == "warning":
            score -= 15
        else:
            score -= 5
    return max(0, score)


def _readiness_status(findings: list[dict[str, Any]]) -> str:
    severities = {finding["severity"] for finding in findings}
    codes = {finding["code"] for finding in findings}
    if "error" in severities:
        return "not_ready"
    if "possibly_multiple_questions" in codes:
        return "possibly_multiple_questions"
    if "vague_terms" in codes or "possibly_too_broad" in codes or "mphil_scope_warning" in codes:
        return "needs_scope"
    if "missing_context_marker" in codes or "too_short" in codes:
        return "needs_context"
    if findings:
        return "ready_for_review"
    return "ready_for_review"


def approve_research_question(workspace: Path, rq_id: str) -> None:
    approved_path, candidates_path, _rejected_path = _paths(workspace)
    approved_doc = read_yaml(approved_path)
    candidates_doc = read_yaml(candidates_path)
    approved = list(approved_doc.get("research_questions", []))
    candidates = list(candidates_doc.get("candidates", []))
    item = _find_and_remove(candidates, rq_id)
    if item is None:
        raise ValueError(f"Unknown candidate research question: {rq_id}")
    item.pop("status", None)
    approved.append(item)
    approved_doc["research_questions"] = approved
    candidates_doc["candidates"] = candidates
    write_yaml(approved_path, approved_doc)
    write_yaml(candidates_path, candidates_doc)
    record_progress_event(workspace, kind="rq_approved", entity_id=rq_id)


def reject_research_question(workspace: Path, rq_id: str, *, reason: str = "") -> None:
    _move_to_rejected(workspace, rq_id, status="rejected", reason=reason)


def archive_research_question(workspace: Path, rq_id: str, *, reason: str = "") -> None:
    _move_to_rejected(workspace, rq_id, status="archived", reason=reason)


def _move_to_rejected(workspace: Path, rq_id: str, *, status: str, reason: str) -> None:
    approved_path, candidates_path, rejected_path = _paths(workspace)
    approved_doc = read_yaml(approved_path)
    candidates_doc = read_yaml(candidates_path)
    rejected_doc = read_yaml(rejected_path)
    approved = list(approved_doc.get("research_questions", []))
    candidates = list(candidates_doc.get("candidates", []))
    item = _find_and_remove(candidates, rq_id) or _find_and_remove(approved, rq_id)
    if item is None:
        raise ValueError(f"Unknown research question: {rq_id}")
    item["status"] = status
    item["reason"] = reason
    rejected = list(rejected_doc.get("rejected", []))
    rejected.append(item)
    approved_doc["research_questions"] = approved
    candidates_doc["candidates"] = candidates
    rejected_doc["rejected"] = rejected
    write_yaml(approved_path, approved_doc)
    write_yaml(candidates_path, candidates_doc)
    write_yaml(rejected_path, rejected_doc)
    record_progress_event(workspace, kind=f"rq_{status}", entity_id=rq_id, detail=reason)
