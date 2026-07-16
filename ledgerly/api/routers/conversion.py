from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ApiError, ok
from ledgerly.engine.conversion import convert_sources, ocr_readiness_report, processing_issue_report


router = APIRouter()


class ConversionRunRequest(BaseModel):
    status: Optional[str] = None
    allow_ocr: bool = False


@router.post("/run")
def conversion_run(payload: ConversionRunRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        result = convert_sources(workspace, status=payload.status, allow_ocr=payload.allow_ocr)
    except ValueError as exc:
        raise ApiError("invalid_conversion_request", str(exc)) from exc
    return ok(
        {
            "processed": result.processed,
            "converted": result.converted,
            "skipped": result.skipped,
            "failed": result.failed,
            "results": [
                {
                    "source_id": item.source_id,
                    "status": item.status,
                    "output_path": str(item.output_path) if item.output_path else None,
                    "error": item.error,
                }
                for item in result.results
            ],
        }
    )


@router.get("/ocr-readiness")
def conversion_ocr_readiness(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(ocr_readiness_report(workspace))


@router.get("/processing-issues")
def conversion_processing_issues(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(processing_issue_report(workspace))
