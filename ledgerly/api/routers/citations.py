from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ApiError, ok
from ledgerly.engine.citations import apply_citation_plan, create_citation_plan, set_citation_plan_insertion_review_status
from ledgerly.engine.references import CITATION_STYLES


router = APIRouter()


class CitationPlanRequest(BaseModel):
    target: str
    source_paths: list[str] = []
    guideline_ids: list[str] = []
    use_default_guidelines: bool = True
    allow_candidate_citations: bool = False
    citation_style: str = "apa7"


@router.post("/plan")
def citations_plan(payload: CitationPlanRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    if payload.citation_style not in CITATION_STYLES:
        raise ApiError(
            "invalid_citation_style",
            f"Unknown citation style: {payload.citation_style}. Expected one of: {', '.join(sorted(CITATION_STYLES))}",
        )
    try:
        result = create_citation_plan(
            workspace,
            payload.target,
            source_paths=[Path(p) for p in payload.source_paths] or None,
            guideline_ids=payload.guideline_ids or None,
            use_default_guidelines=payload.use_default_guidelines,
            allow_candidate_citations=payload.allow_candidate_citations,
            citation_style=payload.citation_style,
        )
    except ValueError as exc:
        raise ApiError("invalid_citation_plan_target", str(exc)) from exc
    return ok(
        {
            "plan": result.plan,
            "yaml_path": str(result.yaml_path),
            "markdown_path": str(result.markdown_path),
        }
    )


class CitationInsertionReviewRequest(BaseModel):
    target: str
    sentence_index: int
    source_id: str
    review_status: str
    plan_path: Optional[str] = None


@router.post("/plan/insertion-review")
def citations_plan_insertion_review(
    payload: CitationInsertionReviewRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    """Set one citation-plan insertion's review_status via the API.

    `create_citation_plan`/`apply_citation_plan` were designed around a
    human hand-editing the plan YAML on disk, which a browser-based
    reviewer has no way to do — this is that missing API equivalent,
    mirroring `POST /api/v1/artefacts/cross-reference/candidate-review`.
    Deliberately named `insertion-review`, not `review`, to avoid the same
    class of path collision that route's naming had to work around (this
    router has no `{plan_id}/review`-shaped route today, but the naming
    stays consistent regardless).
    """
    try:
        insertion = set_citation_plan_insertion_review_status(
            workspace,
            payload.target,
            payload.sentence_index,
            payload.source_id,
            payload.review_status,
            plan_path=Path(payload.plan_path) if payload.plan_path else None,
        )
    except ValueError as exc:
        status_code = 404 if "does not exist" in str(exc) or "No insertion found" in str(exc) else 400
        raise ApiError("citation_insertion_review_failed", str(exc), status_code=status_code) from exc
    return ok(insertion)


class CitationApplyRequest(BaseModel):
    target: str
    plan_path: Optional[str] = None


@router.post("/apply")
def citations_apply(payload: CitationApplyRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        result = apply_citation_plan(
            workspace,
            payload.target,
            plan_path=Path(payload.plan_path) if payload.plan_path else None,
        )
    except ValueError as exc:
        raise ApiError("citation_apply_failed", str(exc)) from exc
    return ok(
        {
            "applied": result.applied,
            "skipped": result.skipped,
            "output_path": str(result.output_path),
            "report_path": str(result.report_path),
            "version_id": result.version_id,
            "source_snapshot_version_id": result.source_snapshot_version_id,
        }
    )
