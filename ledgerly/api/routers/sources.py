from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ApiError, ok
from ledgerly.core.yamlio import read_yaml
from ledgerly.engine.sources import (
    add_source_tag,
    list_sources,
    scan_sources,
    set_source_note,
    set_source_status,
    source_review_report,
)
from ledgerly.engine.watch import write_watch_report


router = APIRouter()


@router.get("/watch")
def sources_watch(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    """Detect unregistered files in the configured source folder without registering them."""
    output_path = write_watch_report(workspace)
    return ok(read_yaml(output_path))


@router.get("")
def sources_list(
    workspace: Path = Depends(resolve_workspace),
    status: Optional[str] = Query(None),
) -> dict[str, Any]:
    try:
        rows = list_sources(workspace, status=status)
    except ValueError as exc:
        raise ApiError("invalid_source_status", str(exc)) from exc
    return ok(rows)


class SourcesScanRequest(BaseModel):
    source_root: str
    provider: str = "local_folder"
    initial_status: str = "pending_review"


@router.post("/scan")
def sources_scan(payload: SourcesScanRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        result = scan_sources(
            workspace,
            Path(payload.source_root).expanduser(),
            provider=payload.provider,
            initial_status=payload.initial_status,
        )
    except ValueError as exc:
        raise ApiError("invalid_scan_request", str(exc)) from exc
    return ok(
        {
            "processed": result.processed,
            "added": result.added,
            "duplicates": result.duplicates,
            "skipped": result.skipped,
        }
    )


class SourceStatusRequest(BaseModel):
    new_status: str
    ignore_reason: Optional[str] = None


@router.post("/{source_id}/status")
def sources_set_status(
    source_id: str,
    payload: SourceStatusRequest,
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    try:
        set_source_status(
            workspace,
            source_id=source_id,
            new_status=payload.new_status,
            ignore_reason=payload.ignore_reason,
        )
    except ValueError as exc:
        if str(exc).startswith("Unknown source_id"):
            raise ApiError("unknown_source_id", str(exc), status_code=404) from exc
        raise ApiError("invalid_source_status_change", str(exc)) from exc
    return ok({"source_id": source_id, "status": payload.new_status})


class SourceNoteRequest(BaseModel):
    note: str


@router.post("/{source_id}/note")
def sources_set_note(
    source_id: str,
    payload: SourceNoteRequest,
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    try:
        set_source_note(workspace, source_id=source_id, note=payload.note)
    except ValueError as exc:
        raise ApiError("unknown_source_id", str(exc), status_code=404) from exc
    return ok({"source_id": source_id})


class SourceTagRequest(BaseModel):
    tag: str


@router.post("/{source_id}/tags")
def sources_add_tag(
    source_id: str,
    payload: SourceTagRequest,
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    try:
        add_source_tag(workspace, source_id=source_id, tag=payload.tag)
    except ValueError as exc:
        raise ApiError("invalid_source_tag", str(exc), status_code=404) from exc
    return ok({"source_id": source_id, "tag": payload.tag})


@router.get("/report")
def sources_report(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(source_review_report(workspace))
