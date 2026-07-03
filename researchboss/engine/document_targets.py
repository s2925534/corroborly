from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from researchboss.engine.artefact_creation import SUPPORTED_ARTEFACT_TYPES
from researchboss.engine.artefacts import list_artefacts


PRIMARY_OUTPUT_ALIASES: dict[str, str] = {
    "thesis": "artefacts/thesis",
    "paper": "artefacts/papers",
    "papers": "artefacts/papers",
    "report": "artefacts/reports",
    "reports": "artefacts/reports",
    "presentation": "artefacts/presentations",
    "presentations": "artefacts/presentations",
    "notes": "artefacts/notes",
    "note": "artefacts/notes",
}

DOCUMENT_TARGET_EXTENSIONS = {
    ".doc",
    ".docx",
    ".html",
    ".htm",
    ".md",
    ".odt",
    ".pdf",
    ".rtf",
    ".txt",
}


@dataclass(frozen=True)
class DocumentTarget:
    target: str
    kind: str
    path: Path
    source: str
    artefact_id: str | None = None
    artefact_title: str | None = None
    artefact_type: str | None = None


def resolve_document_target(workspace: Path, target: str, *, cwd: Path | None = None) -> DocumentTarget:
    """Resolve a future validation/citation target without modifying workspace state."""
    stripped_target = target.strip()
    if not stripped_target:
        raise ValueError("Document target is required.")

    workspace = workspace.resolve()
    cwd = (cwd or Path.cwd()).resolve()

    path_target = _resolve_existing_path(stripped_target, workspace=workspace, cwd=cwd)
    if path_target is not None:
        return DocumentTarget(
            target=stripped_target,
            kind="file_path",
            path=path_target,
            source="path",
        )

    artefacts = list_artefacts(workspace)
    registry_target = _resolve_registry_target(stripped_target, workspace=workspace, artefacts=artefacts)
    if registry_target is not None:
        return registry_target

    artefact_type_target = _resolve_supported_artefact_type(stripped_target, workspace=workspace, artefacts=artefacts)
    if artefact_type_target is not None:
        return artefact_type_target

    alias_target = _resolve_primary_alias(stripped_target, workspace=workspace, artefacts=artefacts)
    if alias_target is not None:
        return alias_target

    raise ValueError(f"Could not resolve document target: {stripped_target}")


def _resolve_existing_path(target: str, *, workspace: Path, cwd: Path) -> Path | None:
    raw_path = Path(target).expanduser()
    candidates = [raw_path] if raw_path.is_absolute() else [cwd / raw_path, workspace / raw_path]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _resolve_registry_target(
    target: str,
    *,
    workspace: Path,
    artefacts: list[dict[str, Any]],
) -> DocumentTarget | None:
    normalized_target = _normalize(target)
    id_matches = [item for item in artefacts if str(item.get("id", "")).strip() == target]
    if id_matches:
        return _target_from_artefact(target, id_matches[0], workspace=workspace, source="artefact_id")

    title_matches = [item for item in artefacts if _normalize(str(item.get("title", ""))) == normalized_target]
    if len(title_matches) > 1:
        titles = ", ".join(str(item.get("id", "unknown")) for item in title_matches)
        raise ValueError(f"Document target title is ambiguous: {target}. Matching artefacts: {titles}")
    if title_matches:
        return _target_from_artefact(target, title_matches[0], workspace=workspace, source="artefact_title")
    return None


def _resolve_supported_artefact_type(
    target: str,
    *,
    workspace: Path,
    artefacts: list[dict[str, Any]],
) -> DocumentTarget | None:
    normalized_target = _normalize(target)
    type_matches = [
        item
        for item in artefacts
        if _normalize(str(item.get("type", ""))) == normalized_target
        and normalized_target in {_normalize(kind) for kind in SUPPORTED_ARTEFACT_TYPES}
    ]
    if len(type_matches) > 1:
        ids = ", ".join(str(item.get("id", "unknown")) for item in type_matches)
        raise ValueError(f"Document target artefact type is ambiguous: {target}. Matching artefacts: {ids}")
    if type_matches:
        return _target_from_artefact(target, type_matches[0], workspace=workspace, source="artefact_type")

    for artefact_type, relative_path in SUPPORTED_ARTEFACT_TYPES.items():
        if _normalize(artefact_type) == normalized_target:
            path = (workspace / relative_path).resolve()
            if path.exists() and path.is_file():
                return DocumentTarget(
                    target=target,
                    kind="artefact_type",
                    path=path,
                    source="supported_artefact_type",
                    artefact_type=artefact_type,
                )
    return None


def _resolve_primary_alias(
    target: str,
    *,
    workspace: Path,
    artefacts: list[dict[str, Any]],
) -> DocumentTarget | None:
    normalized_target = _normalize(target)
    alias_dir = PRIMARY_OUTPUT_ALIASES.get(normalized_target)
    if alias_dir is None:
        return None

    artefact_matches = [
        item
        for item in artefacts
        if _normalize(str(item.get("type", ""))) in {normalized_target, normalized_target.rstrip("s")}
    ]
    if len(artefact_matches) > 1:
        ids = ", ".join(str(item.get("id", "unknown")) for item in artefact_matches)
        raise ValueError(f"Document target alias is ambiguous: {target}. Matching artefacts: {ids}")
    if artefact_matches:
        return _target_from_artefact(target, artefact_matches[0], workspace=workspace, source="primary_output_alias")

    files = _document_files(workspace / alias_dir)
    if len(files) > 1:
        names = ", ".join(path.name for path in files)
        raise ValueError(f"Document target alias is ambiguous: {target}. Matching files: {names}")
    if files:
        return DocumentTarget(
            target=target,
            kind="primary_output_alias",
            path=files[0],
            source="primary_output_alias",
        )
    return None


def _target_from_artefact(
    target: str,
    artefact: dict[str, Any],
    *,
    workspace: Path,
    source: str,
) -> DocumentTarget:
    path_value = str(artefact.get("path", "")).strip()
    if not path_value:
        raise ValueError(f"Artefact has no path: {artefact.get('id', 'unknown')}")
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return DocumentTarget(
        target=target,
        kind="artefact",
        path=path.resolve(),
        source=source,
        artefact_id=str(artefact.get("id")) if artefact.get("id") else None,
        artefact_title=str(artefact.get("title")) if artefact.get("title") else None,
        artefact_type=str(artefact.get("type")) if artefact.get("type") else None,
    )


def _document_files(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(
        path.resolve()
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in DOCUMENT_TARGET_EXTENSIONS
    )


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())
