from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ApiError, ok
from ledgerly.engine.external_search import (
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
