from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from researchboss.api.deps import resolve_workspace
from researchboss.api.envelope import ApiError, ok
from researchboss.engine.guidelines import (
    guideline_conflict_report,
    list_guidelines,
    register_guideline,
    set_default_guidelines,
)


router = APIRouter()


@router.get("")
def guidelines_list(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_guidelines(workspace))


class GuidelineRegisterRequest(BaseModel):
    source: str
    title: Optional[str] = None
    scopes: list[str] = []


@router.post("")
def guidelines_register(payload: GuidelineRegisterRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        result = register_guideline(
            workspace,
            payload.source,
            title=payload.title,
            scopes=payload.scopes or None,
        )
    except ValueError as exc:
        raise ApiError("invalid_guideline_source", str(exc)) from exc
    return ok(
        {
            "record": result.record,
            "snapshot_path": str(result.snapshot_path),
            "text_path": str(result.text_path),
        }
    )


class GuidelineDefaultsRequest(BaseModel):
    guideline_ids: list[str]


@router.post("/defaults")
def guidelines_set_defaults(
    payload: GuidelineDefaultsRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    try:
        result = set_default_guidelines(workspace, payload.guideline_ids)
    except ValueError as exc:
        raise ApiError("invalid_guideline_ids", str(exc)) from exc
    return ok(result)


@router.get("/conflicts")
def guidelines_conflicts(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(guideline_conflict_report(workspace))
