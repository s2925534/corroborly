from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ok
from ledgerly.engine.digest import mark_visited, since_last_visit_digest
from ledgerly.engine.progress_log import research_progress_report
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


@router.get("/research-progress")
def reports_research_progress(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(research_progress_report(workspace))


@router.get("/digest")
def reports_digest(mark_seen: bool = True, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    """What changed since the workspace was last visited -- see
    `ledgerly.engine.digest.since_last_visit_digest`. `mark_seen=false`
    computes the digest without updating the last-visited timestamp, a
    read-only peek."""
    report = since_last_visit_digest(workspace)
    if mark_seen:
        mark_visited(workspace)
    return ok(report)
