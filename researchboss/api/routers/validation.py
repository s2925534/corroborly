from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from researchboss.api.deps import resolve_workspace
from researchboss.api.envelope import ApiError, ok
from researchboss.engine.doc_validation import validate_document


router = APIRouter()


class ValidationRunRequest(BaseModel):
    target: str
    source_paths: list[str] = []
    guideline_ids: list[str] = []
    use_default_guidelines: bool = True


@router.post("/run")
def validation_run(payload: ValidationRunRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        result = validate_document(
            workspace,
            payload.target,
            source_paths=[Path(p) for p in payload.source_paths] or None,
            guideline_ids=payload.guideline_ids or None,
            use_default_guidelines=payload.use_default_guidelines,
        )
    except ValueError as exc:
        raise ApiError("invalid_validation_target", str(exc)) from exc
    return ok(
        {
            "report": result.report,
            "yaml_path": str(result.yaml_path),
            "markdown_path": str(result.markdown_path),
        }
    )
