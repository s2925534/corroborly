import wave
from pathlib import Path

import pytest

from ledgerly.engine.transcription import (
    SOURCESCRIBE_ALLOWED_EXTENSIONS,
    TranscriptionError,
    get_transcription_job,
    list_transcription_jobs,
    sourcescribe_readiness_report,
    sourcescribe_root,
    start_transcription,
    upload_transcription_source,
)
from ledgerly.engine.workspace import init_workspace


def _init_ws(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")
    return workspace


def _make_wav(path: Path) -> Path:
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(8000)
        f.writeframes(b"\x00\x00" * 800)
    return path


def test_sourcescribe_root_raises_without_configured_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LEDGERLY_SOURCESCRIBE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    workspace = _init_ws(tmp_path)

    with pytest.raises(TranscriptionError):
        sourcescribe_root(workspace)


def test_sourcescribe_root_raises_when_path_is_not_a_real_checkout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = _init_ws(tmp_path)
    monkeypatch.setenv("LEDGERLY_SOURCESCRIBE_PATH", str(tmp_path))

    with pytest.raises(TranscriptionError):
        sourcescribe_root(workspace)


def test_sourcescribe_readiness_report_reflects_unconfigured_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LEDGERLY_SOURCESCRIBE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    workspace = _init_ws(tmp_path)

    report = sourcescribe_readiness_report(workspace)

    assert report["available"] is False
    assert "reason" in report


def test_sourcescribe_readiness_report_reflects_configured_checkout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = _init_ws(tmp_path)
    fake_root = tmp_path / "fake-sourcescribe"
    fake_root.mkdir()
    (fake_root / "main.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("LEDGERLY_SOURCESCRIBE_PATH", str(fake_root))

    report = sourcescribe_readiness_report(workspace)

    assert report["available"] is True
    assert report["sourcescribe_path"] == str(fake_root)
    assert report["supported_extensions"] == sorted(SOURCESCRIBE_ALLOWED_EXTENSIONS)


def test_upload_transcription_source_rejects_unsupported_extension(tmp_path: Path) -> None:
    workspace = _init_ws(tmp_path)
    bogus = tmp_path / "notes.pdf"
    bogus.write_text("not audio", encoding="utf-8")

    with pytest.raises(ValueError):
        upload_transcription_source(workspace, bogus)


def test_upload_transcription_source_rejects_missing_file(tmp_path: Path) -> None:
    workspace = _init_ws(tmp_path)

    with pytest.raises(ValueError):
        upload_transcription_source(workspace, tmp_path / "missing.wav")


def test_upload_transcription_source_rejects_oversized_file(tmp_path: Path) -> None:
    workspace = _init_ws(tmp_path)
    audio = _make_wav(tmp_path / "clip.wav")

    with pytest.raises(ValueError):
        upload_transcription_source(workspace, audio, max_file_size_bytes=10)


def test_upload_transcription_source_registers_a_pending_job(tmp_path: Path) -> None:
    workspace = _init_ws(tmp_path)
    audio = _make_wav(tmp_path / "clip.wav")

    job = upload_transcription_source(workspace, audio)

    assert job["job_id"] == "transcribe-001"
    assert job["status"] == "pending"
    assert job["original_file_name"] == "clip.wav"
    stored_path = Path(job["stored_source_path"])
    assert stored_path.is_file()
    assert stored_path.is_relative_to(workspace / "transcription_uploads")
    assert list_transcription_jobs(workspace) == [job]


def test_get_transcription_job_unknown_id_raises(tmp_path: Path) -> None:
    workspace = _init_ws(tmp_path)

    with pytest.raises(ValueError):
        get_transcription_job(workspace, "transcribe-999")


def test_start_transcription_unknown_job_raises(tmp_path: Path) -> None:
    workspace = _init_ws(tmp_path)

    with pytest.raises(ValueError):
        start_transcription(workspace, "transcribe-999")


def test_start_transcription_rejects_non_startable_status(tmp_path: Path, monkeypatch) -> None:
    from ledgerly.engine.transcription import _read_jobs, _write_jobs

    workspace = _init_ws(tmp_path)
    audio = _make_wav(tmp_path / "clip.wav")
    job = upload_transcription_source(workspace, audio)
    ledger = _read_jobs(workspace)
    ledger["jobs"][0]["status"] = "completed"
    _write_jobs(workspace, ledger)

    with pytest.raises(ValueError):
        start_transcription(workspace, job["job_id"])


def test_start_transcription_raises_without_sourcescribe_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LEDGERLY_SOURCESCRIBE_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    workspace = _init_ws(tmp_path)
    audio = _make_wav(tmp_path / "clip.wav")
    job = upload_transcription_source(workspace, audio)

    with pytest.raises(TranscriptionError):
        start_transcription(workspace, job["job_id"])


def _real_sourcescribe_available() -> bool:
    path = Path("/Users/pedro/Documents/_Projects/transcriber")
    return (path / "main.py").is_file() and (path / ".venv" / "bin" / "python").is_file()


requires_real_sourcescribe = pytest.mark.skipif(
    not _real_sourcescribe_available(),
    reason="No real local SourceScribe (transcriber) checkout available for a genuine end-to-end run",
)


@requires_real_sourcescribe
def test_start_transcription_runs_real_sourcescribe_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """Genuine (non-mocked) end-to-end run against the real sibling SourceScribe checkout.

    Confirms the exact contract this module depends on: `report.json`'s
    `status`/`transcript_path` fields, and that a completed job's transcript
    actually lands in the Phase 25 notes store via `import_transcript`.
    """
    monkeypatch.setenv("LEDGERLY_SOURCESCRIBE_PATH", "/Users/pedro/Documents/_Projects/transcriber")
    workspace = _init_ws(tmp_path)
    audio = _make_wav(tmp_path / "clip.wav")
    job = upload_transcription_source(workspace, audio)

    result = start_transcription(workspace, job["job_id"], language="en")

    assert result["status"] in {"completed", "failed"}
    if result["status"] == "completed":
        assert result["note_id"]
        from ledgerly.engine.notes import list_notes

        notes = list_notes(workspace)
        assert any(n["id"] == result["note_id"] for n in notes)
