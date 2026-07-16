from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ok
from ledgerly.engine.project_log import timeline_report
from ledgerly.engine.relationships import citation_relationship_map
from ledgerly.engine.report_schemas import export_report_schemas
from ledgerly.engine.reports import generate_workspace_report


router = APIRouter()


@router.get("/workspace")
def reports_workspace(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    report_path = generate_workspace_report(workspace)
    return ok({"report_path": str(report_path), "markdown": report_path.read_text(encoding="utf-8")})


@router.get("/timeline")
def reports_timeline(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(timeline_report(workspace))


@router.get("/schemas")
def reports_schemas(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    result = export_report_schemas(workspace)
    return ok(
        {
            "yaml_path": str(result.yaml_path),
            "markdown_path": str(result.markdown_path),
            "schema_count": result.schema_count,
        }
    )


@router.get("/citation-relationships")
def reports_citation_relationships(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(citation_relationship_map(workspace))
