from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from corroborly.api.deps import resolve_workspace
from corroborly.api.envelope import ApiError, ok
from corroborly.engine.ai import OpenAiError, ai_workspace_report, openai_credentials
from corroborly.engine.external_search import (
    ExternalSearchError,
    external_candidate_deduplication_report,
    external_candidate_zotero_match_report,
    external_search_evidence_validation_report,
    external_search_run_comparison_report,
    filter_unused_queries,
    generate_search_query_plan,
    import_external_candidates,
    write_high_signal_candidate_report,
)


router = APIRouter()


class SearchPlanRequest(BaseModel):
    max_queries: int = 20
    strategy: str = "balanced"
    params_file: Optional[str] = None
    unused_only: bool = False


@router.post("/plan")
def search_plan(payload: SearchPlanRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    """Generate a deterministic external-search query plan without calling any external API."""
    try:
        plan = generate_search_query_plan(
            workspace,
            max_queries=payload.max_queries,
            strategy=payload.strategy,
            params_file=Path(payload.params_file) if payload.params_file else None,
        )
    except ExternalSearchError as exc:
        raise ApiError("search_plan_failed", str(exc), status_code=400) from exc
    if payload.unused_only:
        plan = {**plan, "queries": filter_unused_queries(workspace, plan["queries"])}
    return ok(plan)


@router.get("/reports")
def search_reports(limit: int = 50, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    """Regenerate deterministic external-search reports (high-signal, duplicates, Zotero matches, evidence, run comparison) from local candidate registers."""
    high_signal = write_high_signal_candidate_report(workspace, limit=limit)
    duplicates = external_candidate_deduplication_report(workspace)
    zotero_matches = external_candidate_zotero_match_report(workspace)
    evidence = external_search_evidence_validation_report(workspace)
    comparison = external_search_run_comparison_report(workspace)
    return ok(
        {
            "high_signal": high_signal,
            "duplicates": duplicates,
            "zotero_matches": zotero_matches,
            "evidence": evidence,
            "comparison": comparison,
        }
    )


class SearchImportCandidatesRequest(BaseModel):
    candidate_ids: list[str]


@router.post("/import-candidates")
def search_import_candidates(
    payload: SearchImportCandidatesRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    """Import reviewed external candidates into the source register as pending-review metadata-only sources."""
    try:
        report = import_external_candidates(workspace, payload.candidate_ids)
    except ExternalSearchError as exc:
        raise ApiError("search_import_candidates_failed", str(exc), status_code=400) from exc
    return ok(report)


class AiQueryPlanRequest(BaseModel):
    ai: bool = False
    external_search: bool = False
    max_sources: int = 10
    max_excerpt_chars: int = 1200


@router.post("/ai-query-plan")
def search_ai_query_plan(payload: AiQueryPlanRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    """AI-assisted external-search query suggestions, never executed automatically. Requires both `ai: true` and
    `external_search: true` — same double opt-in the CLI's `--ai --external-search` requires."""
    if not payload.ai:
        raise ApiError("ai_not_enabled", 'Set "ai": true to explicitly opt in to this AI action.', status_code=400)
    if not payload.external_search:
        raise ApiError(
            "external_search_not_enabled",
            'Set "external_search": true to explicitly opt in to external-search planning.',
            status_code=400,
        )
    try:
        credentials = openai_credentials(workspace)
    except OpenAiError as exc:
        raise ApiError("openai_not_configured", str(exc), status_code=503) from exc
    try:
        report = ai_workspace_report(
            workspace,
            credentials,
            kind="query_generation",
            max_sources=payload.max_sources,
            max_excerpt_chars=payload.max_excerpt_chars,
        )
    except OpenAiError as exc:
        raise ApiError("ai_call_failed", str(exc), status_code=502) from exc
    return ok(report)


class AiCandidateReviewRequest(BaseModel):
    ai: bool = False
    external_search: bool = False
    full_source_document_ai: bool = False
    max_sources: int = 10
    max_excerpt_chars: int = 1200


@router.post("/ai-candidate-review")
def search_ai_candidate_review(
    payload: AiCandidateReviewRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    """AI-assisted candidate relevance/novelty review, from candidate metadata and abstracts only unless
    `full_source_document_ai: true` is separately and explicitly set — the same two-tier opt-in the CLI's
    `--ai --external-search [--full-source-document-ai]` requires."""
    if not payload.ai:
        raise ApiError("ai_not_enabled", 'Set "ai": true to explicitly opt in to this AI action.', status_code=400)
    if not payload.external_search:
        raise ApiError(
            "external_search_not_enabled",
            'Set "external_search": true to explicitly opt in to external candidate review.',
            status_code=400,
        )
    try:
        credentials = openai_credentials(workspace)
    except OpenAiError as exc:
        raise ApiError("openai_not_configured", str(exc), status_code=503) from exc
    try:
        report = ai_workspace_report(
            workspace,
            credentials,
            kind="candidate_validation",
            max_sources=payload.max_sources,
            max_excerpt_chars=payload.max_excerpt_chars,
        )
    except OpenAiError as exc:
        raise ApiError("ai_call_failed", str(exc), status_code=502) from exc
    report["full_source_document_ai_opt_in"] = payload.full_source_document_ai
    report["full_text_mode"] = "explicit_opt_in" if payload.full_source_document_ai else "metadata_and_abstracts_only"
    return ok(report)
