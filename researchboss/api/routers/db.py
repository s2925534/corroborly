from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from researchboss.api.deps import resolve_workspace
from researchboss.api.envelope import ok
from researchboss.engine.database import (
    DbCommandResult,
    apply_pending_changes,
    database_privacy_report,
    database_status,
    init_database,
    pending_changes_report,
    rebuild_database,
    sync_database,
)


router = APIRouter()


def _result(result: DbCommandResult) -> dict[str, Any]:
    return {"database_path": str(result.path), "report": result.report}


@router.post("/init")
def db_init(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(_result(init_database(workspace)))


@router.post("/sync")
def db_sync(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(_result(sync_database(workspace)))


@router.get("/status")
def db_status(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(_result(database_status(workspace)))


@router.post("/rebuild")
def db_rebuild(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(_result(rebuild_database(workspace)))


@router.get("/pending")
def db_pending(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(_result(pending_changes_report(workspace)))


class ApplyPendingRequest(BaseModel):
    apply: bool = False


@router.post("/apply-pending")
def db_apply_pending(payload: ApplyPendingRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(_result(apply_pending_changes(workspace, apply=payload.apply)))


@router.get("/privacy")
def db_privacy(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(_result(database_privacy_report(workspace)))
