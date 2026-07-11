from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from researchboss.api.deps import resolve_workspace
from researchboss.api.envelope import ApiError, ok
from researchboss.engine.citations import apply_citation_plan, create_citation_plan


router = APIRouter()


class CitationPlanRequest(BaseModel):
    target: str
    source_paths: list[str] = []
    guideline_ids: list[str] = []
    use_default_guidelines: bool = True
    allow_candidate_citations: bool = False


@router.post("/plan")
def citations_plan(payload: CitationPlanRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        result = create_citation_plan(
            workspace,
            payload.target,
            source_paths=[Path(p) for p in payload.source_paths] or None,
            guideline_ids=payload.guideline_ids or None,
            use_default_guidelines=payload.use_default_guidelines,
            allow_candidate_citations=payload.allow_candidate_citations,
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
