from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ok
from ledgerly.engine.export import export_accepted_source_corpus, export_evidence_bundle
from ledgerly.engine.pdf_merge import pdf_merge_report


router = APIRouter()


@router.post("/evidence")
def export_evidence(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    bundle_path = export_evidence_bundle(workspace)
    return ok({"bundle_path": str(bundle_path)})


@router.post("/corpus")
def export_corpus(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    result = export_accepted_source_corpus(workspace)
    return ok(
        {
            "corpus_path": str(result.corpus_path),
            "manifest_path": str(result.manifest_path),
            "included_count": result.included_count,
            "skipped_count": result.skipped_count,
        }
    )


class MergePdfsRequest(BaseModel):
    write: bool = False
    output: Optional[str] = None


@router.post("/merge-pdfs")
def export_merge_pdfs(payload: MergePdfsRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    result = pdf_merge_report(
        workspace,
        dry_run=not payload.write,
        output=Path(payload.output) if payload.output else None,
    )
    return ok(
        {
            "manifest_path": str(result.manifest_path),
            "csv_path": str(result.csv_path),
            "output_path": str(result.output_path) if result.output_path else None,
            "included": result.included,
            "skipped": result.skipped,
            "failed": result.failed,
            "dry_run": result.dry_run,
        }
    )
