from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from researchboss.core.yamlio import read_yaml, write_yaml


CONVERTIBLE_EXTENSIONS = {".txt"}


@dataclass(frozen=True)
class ConversionResult:
    source_id: str
    status: str
    output_path: Optional[Path]
    error: Optional[str] = None


@dataclass(frozen=True)
class ConversionRunResult:
    processed: int
    converted: int
    skipped: int
    failed: int
    results: list[ConversionResult]


def _load_register(workspace: Path) -> dict[str, Any]:
    return read_yaml(workspace / "source-register.yaml")


def _write_register(workspace: Path, register: dict[str, Any]) -> None:
    write_yaml(workspace / "source-register.yaml", register)


def _conversion_output_path(workspace: Path, source_id: str) -> Path:
    return workspace / "sources_text" / f"{source_id}.txt"


def _convert_txt(source_path: Path, output_path: Path) -> None:
    text = source_path.read_text(encoding="utf-8", errors="replace")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalized, encoding="utf-8")


def convert_source_record(workspace: Path, source: dict[str, Any]) -> ConversionResult:
    source_id = str(source.get("source_id") or "")
    source_path = Path(str(source.get("file_path") or ""))
    extension = source_path.suffix.lower()
    if extension not in CONVERTIBLE_EXTENSIONS:
        source["conversion"] = {
            "status": "not_supported",
            "output_path": None,
            "error": None,
        }
        return ConversionResult(source_id=source_id, status="not_supported", output_path=None)

    output_path = _conversion_output_path(workspace, source_id)
    _convert_txt(source_path, output_path)
    source["conversion"] = {
        "status": "converted",
        "output_path": str(output_path),
        "error": None,
    }
    return ConversionResult(source_id=source_id, status="converted", output_path=output_path)


def convert_sources(workspace: Path, *, status: Optional[str] = None) -> ConversionRunResult:
    register = _load_register(workspace)
    sources = [source for source in register.get("sources", []) if isinstance(source, dict)]
    selected = [source for source in sources if status is None or source.get("status") == status]

    results = [convert_source_record(workspace, source) for source in selected]
    register["sources"] = sources
    _write_register(workspace, register)

    return ConversionRunResult(
        processed=len(results),
        converted=sum(1 for result in results if result.status == "converted"),
        skipped=sum(1 for result in results if result.status == "not_supported"),
        failed=sum(1 for result in results if result.status == "failed"),
        results=results,
    )
