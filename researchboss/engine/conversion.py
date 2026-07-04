from __future__ import annotations

import re
import importlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree

from researchboss.core.yamlio import read_yaml, write_yaml


CONVERTIBLE_EXTENSIONS = {".txt", ".md", ".docx", ".pdf"}


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


def _conversion_failure_path(workspace: Path, source_id: str) -> Path:
    return workspace / "sources_failed" / f"{source_id}.yaml"


def _convert_txt(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(extract_text(source_path), encoding="utf-8")


def _markdown_to_text(markdown: str) -> str:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
    return text


def _convert_md(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(extract_text(source_path), encoding="utf-8")


def _convert_docx(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(extract_text(source_path), encoding="utf-8")


def _extract_docx_text(source_path: Path) -> str:
    with zipfile.ZipFile(source_path) as docx:
        xml_bytes = docx.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = []
        for text_node in paragraph.findall(".//w:t", namespace):
            if text_node.text:
                parts.append(text_node.text)
        if parts:
            paragraphs.append("".join(parts))
    return "\n".join(paragraphs) + ("\n" if paragraphs else "")


def _decode_pdf_text_literal(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\n")
        .replace(r"\t", "\t")
    )


def _extract_pdf_stream_text(stream: str) -> str:
    literals = re.findall(r"\((?:\\.|[^\\)])*\)", stream, flags=re.DOTALL)
    parts = [_decode_pdf_text_literal(literal[1:-1]) for literal in literals]
    return " ".join(part.strip() for part in parts if part.strip())


def _convert_pdf(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(extract_text(source_path), encoding="utf-8")


def _extract_pdf_text(source_path: Path) -> str:
    for extractor in (_extract_pdf_text_pymupdf, _extract_pdf_text_pypdf):
        try:
            text = extractor(source_path)
        except Exception:
            text = None
        if text and text.strip():
            return text
    return _extract_pdf_text_conservative(source_path)


def _extract_pdf_text_pymupdf(source_path: Path) -> str | None:
    fitz = importlib.import_module("fitz")
    doc = fitz.open(str(source_path))
    try:
        pages = []
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text") if hasattr(page, "get_text") else ""
            pages.append(f"--- Page {index} ---\n{text.strip()}")
        return "\n".join(pages).strip() + ("\n" if pages else "")
    finally:
        close = getattr(doc, "close", None)
        if callable(close):
            close()


def _extract_pdf_text_pypdf(source_path: Path) -> str | None:
    try:
        pypdf = importlib.import_module("pypdf")
    except ModuleNotFoundError:
        pypdf = importlib.import_module("PyPDF2")
    reader = pypdf.PdfReader(str(source_path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() if hasattr(page, "extract_text") else ""
        pages.append(f"--- Page {index} ---\n{str(text or '').strip()}")
    return "\n".join(pages).strip() + ("\n" if pages else "")


def _extract_pdf_text_conservative(source_path: Path) -> str:
    raw = source_path.read_bytes().decode("latin-1", errors="ignore")
    streams = re.findall(r"stream\s*(.*?)\s*endstream", raw, flags=re.DOTALL)
    pages = []
    for stream in streams:
        text = _extract_pdf_stream_text(stream)
        if text:
            pages.append(text)
    output_lines = []
    for index, page_text in enumerate(pages or [""], start=1):
        output_lines.append(f"--- Page {index} ---")
        output_lines.append(page_text)
    return "\n".join(output_lines) + "\n"


def extract_text(source_path: Path) -> str:
    extension = source_path.suffix.lower()
    if extension == ".txt":
        text = source_path.read_text(encoding="utf-8", errors="replace")
        return text.replace("\r\n", "\n").replace("\r", "\n")
    if extension == ".md":
        text = source_path.read_text(encoding="utf-8", errors="replace")
        return _markdown_to_text(text)
    if extension == ".docx":
        return _extract_docx_text(source_path)
    if extension == ".pdf":
        return _extract_pdf_text(source_path)
    raise ValueError(f"Unsupported text extraction extension: {extension}")


def convert_source_record(workspace: Path, source: dict[str, Any]) -> ConversionResult:
    source_id = str(source.get("source_id") or "")
    source_path = Path(str(source.get("file_path") or ""))
    extension = source_path.suffix.lower()
    content_hash = source.get("content_hash")
    if extension not in CONVERTIBLE_EXTENSIONS:
        source["conversion"] = {
            "status": "not_supported",
            "output_path": None,
            "content_hash": content_hash,
            "error": None,
        }
        return ConversionResult(source_id=source_id, status="not_supported", output_path=None)

    output_path = _conversion_output_path(workspace, source_id)
    previous = source.get("conversion") if isinstance(source.get("conversion"), dict) else {}
    if (
        previous.get("status") == "converted"
        and previous.get("content_hash") == content_hash
        and previous.get("output_path")
        and Path(str(previous["output_path"])).is_file()
    ):
        source["conversion"] = {
            **previous,
            "status": "skipped_unchanged",
            "error": None,
        }
        return ConversionResult(source_id=source_id, status="skipped_unchanged", output_path=Path(str(previous["output_path"])))

    try:
        if extension == ".txt":
            _convert_txt(source_path, output_path)
        elif extension == ".md":
            _convert_md(source_path, output_path)
        elif extension == ".docx":
            _convert_docx(source_path, output_path)
        elif extension == ".pdf":
            _convert_pdf(source_path, output_path)
    except Exception as exc:
        failure_path = _conversion_failure_path(workspace, source_id)
        failure = {
            "version": 1,
            "source_id": source_id,
            "file_path": str(source_path),
            "content_hash": content_hash,
            "error": str(exc),
        }
        write_yaml(failure_path, failure)
        source["conversion"] = {
            "status": "failed",
            "output_path": None,
            "content_hash": content_hash,
            "failed_path": str(failure_path),
            "error": str(exc),
        }
        return ConversionResult(source_id=source_id, status="failed", output_path=None, error=str(exc))

    source["conversion"] = {
        "status": "converted",
        "output_path": str(output_path),
        "content_hash": content_hash,
        "failed_path": None,
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
        skipped=sum(1 for result in results if result.status in {"not_supported", "skipped_unchanged"}),
        failed=sum(1 for result in results if result.status == "failed"),
        results=results,
    )
