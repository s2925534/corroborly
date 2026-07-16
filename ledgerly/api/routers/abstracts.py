from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ApiError, ok
from ledgerly.engine.abstracts import import_abstract_folder


router = APIRouter()


class AbstractsImportRequest(BaseModel):
    folder: str


@router.post("/import")
def abstracts_import(payload: AbstractsImportRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    """Import local legacy abstract text files into a reviewable candidate register."""
    folder = Path(payload.folder).expanduser()
    if not folder.is_dir():
        raise ApiError("abstracts_folder_not_found", f"Folder does not exist: {payload.folder}", status_code=404)
    result = import_abstract_folder(workspace, folder)
    return ok(
        {
            "processed": result.processed,
            "candidate": result.candidate,
            "filtered": result.filtered,
            "skipped": result.skipped,
            "register_path": str(result.register_path),
        }
    )
