from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from ledgerly.api.deps import resolve_workspace
from ledgerly.api.envelope import ApiError, ok
from ledgerly.engine.transcription import (
    SOURCESCRIBE_ALLOWED_EXTENSIONS,
    TranscriptionError,
    get_transcription_job,
    list_transcription_jobs,
    sourcescribe_readiness_report,
    start_transcription,
    upload_transcription_source,
)


router = APIRouter()

DEFAULT_UPLOAD_MAX_FILE_SIZE_MB = 500.0


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@router.get("/readiness")
def transcription_readiness(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(sourcescribe_readiness_report(workspace))


@router.get("/upload/limits")
def transcription_upload_limits() -> dict[str, Any]:
    return ok(
        {
            "max_file_size_mb": _float_env("LEDGERLY_TRANSCRIBE_MAX_FILE_SIZE_MB", DEFAULT_UPLOAD_MAX_FILE_SIZE_MB),
            "allowed_extensions": sorted(SOURCESCRIBE_ALLOWED_EXTENSIONS),
        }
    )


@router.get("/jobs")
def transcription_jobs_list(workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    return ok(list_transcription_jobs(workspace))


@router.get("/jobs/{job_id}")
def transcription_job_get(job_id: str, workspace: Path = Depends(resolve_workspace)) -> dict[str, Any]:
    try:
        job = get_transcription_job(workspace, job_id)
    except ValueError as exc:
        raise ApiError("unknown_transcription_job", str(exc), status_code=404) from exc
    return ok(job)


@router.post("/upload")
async def transcription_upload(
    file: UploadFile = File(...),
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    """Upload a single audio/video file and register a new pending transcription job.

    A single-file route (not a batch like the artefact upload route) since
    each transcription job runs its own subprocess and produces its own
    note; there is no benefit to batching the upload step itself.
    """
    max_size_bytes = int(
        _float_env("LEDGERLY_TRANSCRIBE_MAX_FILE_SIZE_MB", DEFAULT_UPLOAD_MAX_FILE_SIZE_MB) * 1024 * 1024
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="ledgerly-transcribe-upload-"))
    try:
        safe_name = Path(file.filename or "upload").name or "upload"
        temp_path = temp_dir / safe_name
        written = 0
        with temp_path.open("wb") as handle:
            while written <= max_size_bytes:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)

        try:
            job = upload_transcription_source(workspace, temp_path, max_file_size_bytes=max_size_bytes)
        except ValueError as exc:
            status_code = 400
            raise ApiError("invalid_transcription_upload", str(exc), status_code=status_code) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return ok(job)


class TranscriptionStartRequest(BaseModel):
    language: Optional[str] = None
    ai: bool = False
    prompt: Optional[str] = None


@router.post("/jobs/{job_id}/start")
def transcription_start(
    job_id: str,
    payload: TranscriptionStartRequest,
    workspace: Path = Depends(resolve_workspace),
) -> dict[str, Any]:
    try:
        job = start_transcription(
            workspace, job_id, language=payload.language, use_ai=payload.ai, prompt=payload.prompt
        )
    except ValueError as exc:
        raise ApiError("invalid_transcription_job", str(exc), status_code=404) from exc
    except TranscriptionError as exc:
        raise ApiError("sourcescribe_unavailable", str(exc), status_code=503) from exc
    return ok(job)
