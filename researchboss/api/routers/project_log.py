from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from researchboss.api.deps import resolve_workspace
from researchboss.api.envelope import ok
from researchboss.engine.project_log import (
    add_context_change,
    add_decision,
    add_feedback,
    add_terminology,
    list_context_changes,
    list_decisions,
    list_feedback,
    list_terminology,
)


router = APIRouter()


@router.get("/decisions")
def project_log_list_decisions(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_decisions(workspace))


class DecisionRequest(BaseModel):
    text: str
    reason: str = ""


@router.post("/decisions")
def project_log_add_decision(payload: DecisionRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(add_decision(workspace, payload.text, reason=payload.reason))


@router.get("/terminology")
def project_log_list_terminology(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_terminology(workspace))


class TerminologyRequest(BaseModel):
    term: str
    definition: str


@router.post("/terminology")
def project_log_add_terminology(
    payload: TerminologyRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    return ok(add_terminology(workspace, payload.term, payload.definition))


@router.get("/feedback")
def project_log_list_feedback(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_feedback(workspace))


class FeedbackRequest(BaseModel):
    text: str
    source: str = ""


@router.post("/feedback")
def project_log_add_feedback(payload: FeedbackRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(add_feedback(workspace, payload.text, source=payload.source))


@router.get("/context/changelog")
def project_log_list_context_changes(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_context_changes(workspace))


class ContextChangelogRequest(BaseModel):
    text: str


@router.post("/context/changelog")
def project_log_add_context_change(
    payload: ContextChangelogRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    return ok(add_context_change(workspace, payload.text))
