from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from corroborly.api.deps import resolve_workspace
from corroborly.api.envelope import ApiError, ok
from corroborly.engine.ai import (
    OpenAiCredentials,
    OpenAiError,
    ai_assisted_review,
    ai_novelty_assessment,
    ai_research_question_assessment,
    ai_review_document,
    ai_workspace_report,
    list_ai_usage,
    openai_credentials,
    openai_readiness,
)


router = APIRouter()


def _require_ai(ai: bool, workspace: Path) -> OpenAiCredentials:
    """The web equivalent of the CLI's per-invocation `--ai` flag: no
    session-level or workspace-level AI toggle bypasses this, matching
    docs/api/CONTRACT.md's Future AI Routes sketch. The API key itself is
    always resolved server-side (env var or workspace `.env`) — a request
    body can never supply or override it.
    """
    if not ai:
        raise ApiError("ai_not_enabled", 'Set "ai": true to explicitly opt in to this AI action.', status_code=400)
    try:
        return openai_credentials(workspace)
    except OpenAiError as exc:
        raise ApiError("openai_not_configured", str(exc), status_code=503) from exc


class AiTestRequest(BaseModel):
    ai: bool = False


@router.post("/test")
def ai_test(payload: AiTestRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        credentials = openai_credentials(workspace)
    except OpenAiError as exc:
        raise ApiError("openai_not_configured", str(exc), status_code=503) from exc
    report = openai_readiness(workspace, credentials, live=payload.ai)
    return ok(report)


class AiReviewRequest(BaseModel):
    ai: bool = False
    max_sources: int = 10
    max_excerpt_chars: int = 1200


@router.post("/review")
def ai_review(payload: AiReviewRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    credentials = _require_ai(payload.ai, workspace)
    try:
        report = ai_assisted_review(
            workspace, credentials, max_sources=payload.max_sources, max_excerpt_chars=payload.max_excerpt_chars
        )
    except OpenAiError as exc:
        raise ApiError("ai_call_failed", str(exc), status_code=502) from exc
    return ok(report)


class AiNoveltyRequest(BaseModel):
    ai: bool = False
    max_sources: int = 10
    max_excerpt_chars: int = 1200


@router.post("/novelty")
def ai_novelty(payload: AiNoveltyRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    credentials = _require_ai(payload.ai, workspace)
    try:
        report = ai_novelty_assessment(
            workspace, credentials, max_sources=payload.max_sources, max_excerpt_chars=payload.max_excerpt_chars
        )
    except OpenAiError as exc:
        raise ApiError("ai_call_failed", str(exc), status_code=502) from exc
    return ok(report)


class AiRqAssessRequest(BaseModel):
    ai: bool = False
    rq_id: Optional[str] = None
    max_sources: int = 10
    max_excerpt_chars: int = 1200


@router.post("/rqs/assess")
def ai_rqs_assess(payload: AiRqAssessRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    credentials = _require_ai(payload.ai, workspace)
    try:
        report = ai_research_question_assessment(
            workspace,
            credentials,
            rq_id=payload.rq_id,
            max_sources=payload.max_sources,
            max_excerpt_chars=payload.max_excerpt_chars,
        )
    except OpenAiError as exc:
        status_code = 404 if str(exc).startswith("Unknown research question") else 400
        raise ApiError("ai_rq_assessment_failed", str(exc), status_code=status_code) from exc
    return ok(report)


class AiWorkspaceReportRequest(BaseModel):
    ai: bool = False
    max_sources: int = 10
    max_excerpt_chars: int = 1200


def _workspace_report_route(kind: str):
    def route(payload: AiWorkspaceReportRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
        credentials = _require_ai(payload.ai, workspace)
        try:
            report = ai_workspace_report(
                workspace,
                credentials,
                kind=kind,
                max_sources=payload.max_sources,
                max_excerpt_chars=payload.max_excerpt_chars,
            )
        except OpenAiError as exc:
            raise ApiError("ai_call_failed", str(exc), status_code=502) from exc
        return ok(report)

    return route


# Mirrors the `corroborly ai <name>` CLI commands 1:1, each a thin wrapper
# around `ai_workspace_report` with a fixed `kind` — same engine function
# the CLI's shared `_run_ai_workspace_report` helper calls.
router.add_api_route("/corpus-summary", _workspace_report_route("corpus_summary"), methods=["POST"])
router.add_api_route("/claim-check", _workspace_report_route("claim_checking"), methods=["POST"])
router.add_api_route("/citation-gaps", _workspace_report_route("citation_gaps"), methods=["POST"])
router.add_api_route("/artefact-cross-reference", _workspace_report_route("artefact_cross_reference"), methods=["POST"])
router.add_api_route("/source-relevance", _workspace_report_route("source_relevance"), methods=["POST"])
router.add_api_route("/abstract-screening", _workspace_report_route("abstract_screening"), methods=["POST"])


class AiReviewDocumentRequest(BaseModel):
    target: str
    ai: bool = False
    full_target_document_ai: bool = False
    note_kinds: list[str] = []
    max_sources: int = 10
    max_excerpt_chars: int = 1200


@router.post("/review-document")
def ai_review_document_route(
    payload: AiReviewDocumentRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    if not payload.ai:
        raise ApiError("ai_not_enabled", 'Set "ai": true to explicitly opt in to this AI action.', status_code=400)
    if not payload.full_target_document_ai:
        raise ApiError(
            "full_target_document_ai_not_enabled",
            'Set "full_target_document_ai": true to explicitly allow sending the whole target document to an AI provider.',
            status_code=400,
        )
    try:
        credentials = openai_credentials(workspace)
    except OpenAiError as exc:
        raise ApiError("openai_not_configured", str(exc), status_code=503) from exc
    try:
        report = ai_review_document(
            workspace,
            credentials,
            payload.target,
            note_kinds=payload.note_kinds,
            max_sources=payload.max_sources,
            max_excerpt_chars=payload.max_excerpt_chars,
        )
    except (OpenAiError, ValueError) as exc:
        raise ApiError("ai_review_document_failed", str(exc)) from exc
    return ok(report)


@router.get("/usage-log")
def ai_usage_log(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    """Read-only AI-usage audit log (TODO.md Phase 32) -- no `ai: true` opt-in
    needed since this only reads an already-local record, never calls a
    provider."""
    return ok(list_ai_usage(workspace))
