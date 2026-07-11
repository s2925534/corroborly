from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel

from researchboss.api.deps import resolve_workspace
from researchboss.api.envelope import ApiError, ok
from researchboss.engine.artefact_creation import create_deterministic_artefact
from researchboss.engine.artefacts import (
    artefact_dependency_report,
    list_artefacts,
    register_artefact,
    set_artefact_review_status,
)
from researchboss.engine.cross_reference import apply_cross_reference_links, cross_reference_candidates
from researchboss.engine.sources import ALLOWED_EXTENSIONS
from researchboss.engine.vault import intake_uploaded_artefact_batch


router = APIRouter()

DEFAULT_UPLOAD_MAX_FILES = 25
DEFAULT_UPLOAD_MAX_FILE_SIZE_MB = 50.0


@router.get("")
def artefacts_list(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_artefacts(workspace))


class ArtefactRegisterRequest(BaseModel):
    title: str
    artefact_type: str
    path: str
    linked_sources: list[str] = []
    linked_research_questions: list[str] = []
    requires_user_review: bool = True


@router.post("")
def artefacts_register(payload: ArtefactRegisterRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    record = register_artefact(
        workspace,
        title=payload.title,
        artefact_type=payload.artefact_type,
        path=Path(payload.path),
        linked_sources=payload.linked_sources,
        linked_research_questions=payload.linked_research_questions,
        requires_user_review=payload.requires_user_review,
    )
    return ok(record)


class ArtefactCreateRequest(BaseModel):
    artefact_type: str
    title: Optional[str] = None
    include_maybe: bool = False
    rq_id: Optional[str] = None
    overwrite: bool = False


@router.post("/create")
def artefacts_create(payload: ArtefactCreateRequest, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        result = create_deterministic_artefact(
            workspace,
            payload.artefact_type,
            title=payload.title,
            include_maybe=payload.include_maybe,
            rq_id=payload.rq_id,
            overwrite=payload.overwrite,
        )
    except ValueError as exc:
        status_code = 409 if "already exists" in str(exc) else 400
        raise ApiError("artefact_creation_failed", str(exc), status_code=status_code) from exc
    return ok({"record": result.record, "path": str(result.path)})


class ArtefactReviewRequest(BaseModel):
    status: str


@router.post("/{artefact_id}/review")
def artefacts_review(
    artefact_id: str,
    payload: ArtefactReviewRequest,
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    try:
        set_artefact_review_status(workspace, artefact_id, payload.status)
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Unknown artefact_id") else 400
        raise ApiError("invalid_artefact_review_status", str(exc), status_code=status_code) from exc
    return ok({"artefact_id": artefact_id, "review_status": payload.status})


@router.get("/dependencies")
def artefacts_dependencies(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(artefact_dependency_report(workspace))


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


async def _spool_upload_to_temp(upload: UploadFile, destination: Path, max_bytes: int) -> None:
    """Stream the upload to `destination`, writing at most one chunk past `max_bytes`.

    Deliberately does not enforce the size limit here — writing slightly past
    it lets `intake_uploaded_artefact_batch`'s own file-size check reject the
    file through the normal per-file batch report, so there is exactly one
    place that decides what counts as "too large," while still bounding how
    much of an oversized upload gets written to disk.
    """
    written = 0
    with destination.open("wb") as handle:
        while written <= max_bytes:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            written += len(chunk)


@router.post("/upload")
async def artefacts_upload(
    files: list[UploadFile] = File(...),
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    """Batch-upload externally created artefacts into the document vault.

    Rejects the whole batch up front (no files written) if it exceeds
    RESEARCHBOSS_UPLOAD_MAX_FILES, rather than silently processing only
    some of them. Each file is capped at RESEARCHBOSS_UPLOAD_MAX_FILE_SIZE_MB
    and must have an extension from the same allow-list used for source
    scanning; oversized or disallowed files are reported as rejected, not
    silently dropped.
    """
    max_files = _int_env("RESEARCHBOSS_UPLOAD_MAX_FILES", DEFAULT_UPLOAD_MAX_FILES)
    if len(files) > max_files:
        raise ApiError(
            "upload_batch_too_large",
            f"Batch of {len(files)} files exceeds the configured limit of {max_files} files per batch.",
            status_code=400,
        )

    max_size_bytes = int(_float_env("RESEARCHBOSS_UPLOAD_MAX_FILE_SIZE_MB", DEFAULT_UPLOAD_MAX_FILE_SIZE_MB) * 1024 * 1024)
    temp_dir = Path(tempfile.mkdtemp(prefix="researchboss-upload-"))
    try:
        temp_paths = []
        for index, upload in enumerate(files):
            # Nest each file in its own index-numbered subdirectory (rather than
            # prefixing the filename itself) so two uploads in one batch never
            # collide on disk while the original filename — which becomes the
            # default title for the renamed vault copy — stays exactly as sent.
            safe_name = Path(upload.filename or f"upload-{index}").name or f"upload-{index}"
            file_temp_dir = temp_dir / f"{index:03d}"
            file_temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = file_temp_dir / safe_name
            await _spool_upload_to_temp(upload, temp_path, max_size_bytes)
            temp_paths.append(temp_path)

        try:
            report = intake_uploaded_artefact_batch(
                workspace,
                temp_paths,
                max_files=max_files,
                max_file_size_bytes=max_size_bytes,
                allowed_extensions=ALLOWED_EXTENSIONS,
            )
        except ValueError as exc:
            raise ApiError("upload_batch_too_large", str(exc), status_code=400) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return ok(report)


@router.get("/cross-reference")
def artefacts_cross_reference(
    upload_id: str = Query(...),
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    """Propose deterministic links between an uploaded artefact and existing workspace items.

    Read-only: writes a candidate report but never modifies any artefact,
    source, or claim record.
    """
    try:
        report = cross_reference_candidates(workspace, upload_id)
    except ValueError as exc:
        raise ApiError("unknown_upload_id", str(exc), status_code=404) from exc
    return ok(report)


class CrossReferenceApplyRequest(BaseModel):
    upload_id: str


@router.post("/cross-reference/apply")
def artefacts_cross_reference_apply(
    payload: CrossReferenceApplyRequest, workspace: Path = Depends(resolve_workspace)
) -> dict[str, Any]:
    """Write reviewed cross-reference candidates as metadata on the upload record.

    Only applies candidates whose `review_status` in the persisted report
    (`outputs/recommendations/cross-reference-<upload_id>.yaml`) has been
    hand-edited to "accepted" or "approved" — the same review-before-apply
    pattern citation plans use. Never modifies any artefact, source, or
    claim document's content; see docs/api/CONTRACT.md for why registry
    metadata was chosen over document-content insertion.
    """
    try:
        result = apply_cross_reference_links(workspace, payload.upload_id)
    except ValueError as exc:
        status_code = 404 if "Unknown upload_id" in str(exc) else 400
        raise ApiError("cross_reference_apply_failed", str(exc), status_code=status_code) from exc
    return ok(result)
