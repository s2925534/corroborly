from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.conversion import CONVERTIBLE_EXTENSIONS, extract_text


GUIDELINE_TEXT_EXTENSIONS = CONVERTIBLE_EXTENSIONS | {".html", ".htm"}
GUIDELINE_SCOPES = {
    "validation",
    "citation",
    "structure",
    "style",
    "journal_submission",
    "thesis",
    "supervisor",
    "rubric",
    "all_purpose",
}


@dataclass(frozen=True)
class GuidelineRegistration:
    record: dict[str, Any]
    snapshot_path: Path
    text_path: Path


def register_guideline(
    workspace: Path,
    source: str,
    *,
    title: str | None = None,
    scopes: list[str] | None = None,
) -> GuidelineRegistration:
    source = source.strip()
    if not source:
        raise ValueError("Guideline source is required.")

    registry_path = workspace / "guidelines" / "guidelines.yaml"
    registry = read_yaml(registry_path) if registry_path.exists() else {"version": 1, "guidelines": []}
    guidelines = [item for item in registry.get("guidelines", []) if isinstance(item, dict)]
    guideline_id = f"guideline-{len(guidelines) + 1:03d}"
    resolved_scopes = _validate_scopes(scopes or ["all_purpose"])

    if _is_url(source):
        snapshot_path = _snapshot_remote(workspace, guideline_id, source)
        source_kind = "remote_url"
        original_location = source
    else:
        original_path = Path(source).expanduser()
        if not original_path.exists() or not original_path.is_file():
            raise ValueError(f"Guideline file does not exist: {source}")
        snapshot_path = _snapshot_local(workspace, guideline_id, original_path)
        source_kind = "local_file"
        original_location = str(original_path.resolve())

    text = _guideline_text(snapshot_path)
    text_path = workspace / "guidelines" / "text" / f"{guideline_id}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")

    record = {
        "id": guideline_id,
        "title": title or _default_title(source, snapshot_path),
        "source_kind": source_kind,
        "original_location": original_location,
        "snapshot_path": str(snapshot_path),
        "text_path": str(text_path),
        "file_ext": snapshot_path.suffix.lower().lstrip("."),
        "scopes": resolved_scopes,
        "ai_used": False,
    }
    guidelines.append(record)
    registry["guidelines"] = guidelines
    write_yaml(registry_path, registry)
    return GuidelineRegistration(record=record, snapshot_path=snapshot_path, text_path=text_path)


def list_guidelines(workspace: Path) -> list[dict[str, Any]]:
    registry_path = workspace / "guidelines" / "guidelines.yaml"
    if not registry_path.exists():
        return []
    registry = read_yaml(registry_path)
    return [item for item in registry.get("guidelines", []) if isinstance(item, dict)]


def _snapshot_local(workspace: Path, guideline_id: str, source_path: Path) -> Path:
    snapshot_path = workspace / "guidelines" / "snapshots" / f"{guideline_id}{source_path.suffix.lower()}"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, snapshot_path)
    return snapshot_path


def _snapshot_remote(workspace: Path, guideline_id: str, source: str) -> Path:
    suffix = Path(urlparse(source).path).suffix.lower() or ".html"
    snapshot_path = workspace / "guidelines" / "snapshots" / f"{guideline_id}{suffix}"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(source, timeout=30) as response:
        snapshot_path.write_bytes(response.read())
    return snapshot_path


def _guideline_text(snapshot_path: Path) -> str:
    suffix = snapshot_path.suffix.lower()
    if suffix in {".html", ".htm"}:
        html = snapshot_path.read_text(encoding="utf-8", errors="replace")
        return _html_to_text(html)
    if suffix in GUIDELINE_TEXT_EXTENSIONS:
        return extract_text(snapshot_path)
    raise ValueError(f"Unsupported guideline file extension: {suffix}")


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip() + "\n"


def _default_title(source: str, snapshot_path: Path) -> str:
    if _is_url(source):
        parsed = urlparse(source)
        return Path(parsed.path).name or parsed.netloc or "Remote guideline"
    return snapshot_path.stem.replace("-", " ").replace("_", " ").title()


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def _validate_scopes(scopes: list[str]) -> list[str]:
    normalized = []
    for scope in scopes:
        item = scope.strip().lower().replace("-", "_").replace(" ", "_")
        if item not in GUIDELINE_SCOPES:
            allowed = ", ".join(sorted(GUIDELINE_SCOPES))
            raise ValueError(f"Invalid guideline scope: {scope!r}. Expected one of: {allowed}")
        if item not in normalized:
            normalized.append(item)
    return normalized
