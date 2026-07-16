from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ApiError, ok
from ledgerly.core.yamlio import read_yaml
from ledgerly.engine.claims import (
    add_claim,
    claim_source_validation_report,
    list_claims,
    set_claim_status,
    write_citation_gap_report,
    write_stale_claims_report,
)


router = APIRouter()


@router.get("")
def claims_list(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_claims(workspace))


class ClaimAddRequest(BaseModel):
    text: str
    linked_sources: list[str] = []
    linked_research_questions: list[str] = []


@router.post("")
def claims_add(payload: ClaimAddRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    record = add_claim(
        workspace,
        text=payload.text,
        linked_sources=payload.linked_sources,
        linked_research_questions=payload.linked_research_questions,
    )
    return ok(record)


class ClaimStatusRequest(BaseModel):
    status: str


@router.post("/{claim_id}/status")
def claims_set_status(
    claim_id: str,
    payload: ClaimStatusRequest,
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    try:
        set_claim_status(workspace, claim_id, payload.status)
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Unknown claim_id") else 400
        raise ApiError("invalid_claim_status", str(exc), status_code=status_code) from exc
    return ok({"claim_id": claim_id, "status": payload.status})


@router.get("/gaps")
def claims_gaps(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    report_path = write_citation_gap_report(workspace)
    return ok(read_yaml(report_path))


@router.get("/validate")
def claims_validate(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(claim_source_validation_report(workspace))


@router.get("/stale")
def claims_stale(days: int = 14, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    report_path = write_stale_claims_report(workspace, days=days)
    return ok(read_yaml(report_path))
