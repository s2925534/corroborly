from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ledgerly.core.constants import WORKSPACE_FILES
from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.ai import load_dotenv_values
from ledgerly.engine.notes import import_transcript
from ledgerly.engine.sources import sha256_file

# Matches transcriber_mvp/workflow.py's SUPPORTED_EXTENSIONS in the
# SourceScribe project this module shells out to.
SOURCESCRIBE_ALLOWED_EXTENSIONS = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".ogg",
    ".wav",
    ".webm",
}

JOB_STATUSES = {"pending", "transcribing", "completed", "failed"}


class TranscriptionError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sourcescribe_root(workspace: Path) -> Path:
    """Resolve the SourceScribe (transcriber) project checkout to shell out to.

    Read from LEDGERLY_SOURCESCRIBE_PATH (env var or workspace/cwd .env),
    mirroring how `openai_credentials` resolves OPENAI_API_KEY. SourceScribe
    is a sibling CLI project, invoked via subprocess -- never imported --
    so this only needs to know where its checkout lives, not any secret.
    """
    env_values = load_dotenv_values(Path.cwd() / ".env")
    env_values = {**env_values, **load_dotenv_values(workspace / ".env")}
    raw = os.environ.get("LEDGERLY_SOURCESCRIBE_PATH") or env_values.get("LEDGERLY_SOURCESCRIBE_PATH") or ""
    if not raw:
        raise TranscriptionError(
            "LEDGERLY_SOURCESCRIBE_PATH is not configured; set it to the SourceScribe "
            "(transcriber) project directory to enable transcription."
        )
    root = Path(raw).expanduser()
    if not (root / "main.py").is_file():
        raise TranscriptionError(f"LEDGERLY_SOURCESCRIBE_PATH does not point to a SourceScribe checkout: {root}")
    return root


def _sourcescribe_python(root: Path) -> str:
    venv_python = root / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.is_file() else "python3"


def sourcescribe_readiness_report(workspace: Path) -> dict[str, Any]:
    """Report whether SourceScribe is reachable, without starting a job.

    Mirrors `ledgerly.engine.conversion.ocr_readiness_report`'s pattern of
    a cheap, side-effect-free check a client can call before offering the
    transcription UI at all.
    """
    try:
        root = sourcescribe_root(workspace)
    except TranscriptionError as exc:
        return {"version": 1, "available": False, "reason": str(exc)}
    return {
        "version": 1,
        "available": True,
        "sourcescribe_path": str(root),
        "python_executable": _sourcescribe_python(root),
        "supported_extensions": sorted(SOURCESCRIBE_ALLOWED_EXTENSIONS),
    }


def _ledger_path(workspace: Path) -> Path:
    return workspace / WORKSPACE_FILES.transcription_jobs


def _read_jobs(workspace: Path) -> dict[str, Any]:
    path = _ledger_path(workspace)
    return read_yaml(path) if path.exists() else {}


def _write_jobs(workspace: Path, ledger: dict[str, Any]) -> None:
    write_yaml(_ledger_path(workspace), ledger)


def list_transcription_jobs(workspace: Path) -> list[dict[str, Any]]:
    return _read_jobs(workspace).get("jobs", [])


def get_transcription_job(workspace: Path, job_id: str) -> dict[str, Any]:
    for job in list_transcription_jobs(workspace):
        if job.get("job_id") == job_id:
            return job
    raise ValueError(f"Unknown transcription job_id: {job_id}")


def upload_transcription_source(
    workspace: Path,
    source_path: Path,
    *,
    max_file_size_bytes: Optional[int] = None,
) -> dict[str, Any]:
    """Register an uploaded audio/video file as a new pending transcription job.

    Stored under the top-level `transcription_uploads/` directory, deliberately
    separate from the document vault (per TODO Phase 30: transcription source
    media is not a document-vault artefact).
    """
    if not source_path.is_file():
        raise ValueError(f"Upload source does not exist: {source_path}")
    extension = source_path.suffix.lower()
    if extension not in SOURCESCRIBE_ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension for transcription: {extension or '(none)'}")
    size_bytes = source_path.stat().st_size
    if max_file_size_bytes is not None and size_bytes > max_file_size_bytes:
        raise ValueError(f"Upload of {size_bytes} bytes exceeds the configured limit of {max_file_size_bytes} bytes")

    uploads_dir = workspace / "transcription_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    ledger = _read_jobs(workspace)
    jobs = ledger.setdefault("jobs", [])
    job_id = f"transcribe-{len(jobs) + 1:03d}"
    stored_path = uploads_dir / f"{job_id}{extension}"
    shutil.copy2(source_path, stored_path)

    record = {
        "job_id": job_id,
        "status": "pending",
        "original_file_name": source_path.name,
        "stored_source_path": str(stored_path),
        "size_bytes": size_bytes,
        "content_hash": sha256_file(source_path),
        "created_at": _utc_now(),
    }
    jobs.append(record)
    ledger["jobs"] = jobs
    _write_jobs(workspace, ledger)
    return record


def start_transcription(
    workspace: Path,
    job_id: str,
    *,
    language: Optional[str] = None,
    use_ai: bool = False,
    prompt: Optional[str] = None,
) -> dict[str, Any]:
    """Synchronously run SourceScribe on an uploaded job's source file.

    Shells out to SourceScribe's own CLI (subprocess, never imported) with a
    fresh job-scoped `--source-dir` scratch directory so exactly one
    `completed/*/report.json` is produced per run, unambiguous to glob. Local
    Whisper is the default backend (`use_ai=False`, matching SourceScribe's
    own default); `--ai` is only added when the caller explicitly opts in.
    On success, the resulting transcript is imported into the Phase 25 notes
    store via `import_transcript` -- no AI processing happens on that text
    here, matching that function's own no-fabrication contract.
    """
    ledger = _read_jobs(workspace)
    jobs = ledger.get("jobs", [])
    job = next((item for item in jobs if item.get("job_id") == job_id), None)
    if job is None:
        raise ValueError(f"Unknown transcription job_id: {job_id}")
    if job.get("status") not in {"pending", "failed"}:
        raise ValueError(f"Transcription job {job_id} is not in a startable state (status={job.get('status')}).")

    source_path = Path(str(job.get("stored_source_path") or ""))
    if not source_path.is_file():
        raise TranscriptionError(f"Uploaded source file is missing for job {job_id}: {source_path}")

    root = sourcescribe_root(workspace)
    python_bin = _sourcescribe_python(root)

    job["status"] = "transcribing"
    job["language"] = language
    job["use_ai"] = use_ai
    job["prompt_provided"] = bool(prompt)
    job["started_at"] = _utc_now()
    job.pop("error", None)
    _write_jobs(workspace, ledger)

    scratch_dir = Path(tempfile.mkdtemp(prefix=f"ledgerly-transcribe-{job_id}-"))
    try:
        cmd = [python_bin, str(root / "main.py"), str(source_path), "--source-dir", str(scratch_dir)]
        if language:
            cmd += ["--language", language]
        if use_ai:
            cmd += ["--ai"]
        if prompt:
            cmd += ["--prompt", prompt]

        result = subprocess.run(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode not in (0, 1):
            raise TranscriptionError(
                f"SourceScribe exited with unexpected code {result.returncode} for job {job_id}: "
                f"{(result.stderr or result.stdout).strip()}"
            )

        report_paths = sorted(scratch_dir.glob("completed/*/report.json"))
        if not report_paths:
            job["status"] = "failed"
            job["error"] = (result.stdout or result.stderr).strip() or "SourceScribe produced no output report."
            job["completed_at"] = _utc_now()
            return job

        report = json.loads(report_paths[0].read_text(encoding="utf-8"))
        job["sourcescribe_report"] = {
            key: report.get(key)
            for key in ("status", "backend", "model", "local_model", "language", "diarize", "chunk_seconds")
            if key in report
        }

        if report.get("status") == "completed":
            transcript_path = Path(str(report.get("transcript_path") or ""))
            note = import_transcript(
                workspace,
                transcript_path,
                kind="transcript",
                source_label=str(job.get("original_file_name", "")),
            )
            job["status"] = "completed"
            job["note_id"] = note.get("id")
            job["completed_at"] = _utc_now()
        else:
            job["status"] = "failed"
            job["error"] = report.get("error") or "SourceScribe reported a failed transcription."
            job["completed_at"] = _utc_now()
        return job
    except TranscriptionError as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["completed_at"] = _utc_now()
        raise
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)
        ledger["jobs"] = jobs
        _write_jobs(workspace, ledger)
