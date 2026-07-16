from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.guidelines import list_guidelines, register_guideline, set_default_guidelines

TEMPLATE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def templates_root() -> Path:
    """Where workspace templates live -- deliberately outside any single
    workspace, since a template is meant to seed *future* workspaces, not
    live inside one. `LEDGERLY_TEMPLATES_ROOT` overrides the default
    `~/.ledgerly/templates`, same override pattern as `LEDGERLY_WORKSPACE_ROOT`.
    """
    override = os.environ.get("LEDGERLY_TEMPLATES_ROOT")
    root = Path(override).expanduser() if override else Path.home() / ".ledgerly" / "templates"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_template_name(name: str) -> str:
    name = name.strip()
    if not TEMPLATE_NAME_PATTERN.match(name):
        raise ValueError(
            "Template name must be 1-64 characters of letters, digits, '-', or '_', starting with a letter or digit."
        )
    return name


def list_workspace_templates() -> list[dict[str, Any]]:
    root = templates_root()
    templates = []
    for entry in sorted(root.iterdir()):
        manifest_path = entry / "template.yaml"
        if entry.is_dir() and manifest_path.is_file():
            templates.append(read_yaml(manifest_path))
    return templates


def save_workspace_template(workspace: Path, name: str, *, description: str = "") -> Path:
    """Snapshot a workspace's project-type configuration, citation style,
    default review settings, and full guideline set (registry entries *and*
    the actual snapshotted guideline files, not just references to them) as
    a reusable named template. Never captures workspace content itself
    (sources, claims, notes, etc.) -- only the reusable setup a second,
    similar project would want to start from.
    """
    name = _validate_template_name(name)
    context = read_yaml(workspace / "research-context.yaml")
    project = context.get("project", {}) if isinstance(context.get("project"), dict) else {}
    citation = context.get("citation", {}) if isinstance(context.get("citation"), dict) else {}
    artefacts = context.get("artefacts", {}) if isinstance(context.get("artefacts"), dict) else {}
    sources = context.get("sources", {}) if isinstance(context.get("sources"), dict) else {}
    privacy = context.get("privacy", {}) if isinstance(context.get("privacy"), dict) else {}
    data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}

    template_dir = templates_root() / name
    guidelines_dir = template_dir / "guidelines"
    if guidelines_dir.exists():
        shutil.rmtree(guidelines_dir)
    guidelines_dir.mkdir(parents=True, exist_ok=True)

    source_guidelines = list_guidelines(workspace)
    default_ids = set(context.get("guidelines", {}).get("default_guideline_ids", []) or [])
    template_guidelines = []
    for guideline in source_guidelines:
        snapshot_path = Path(str(guideline.get("snapshot_path", "")))
        if not snapshot_path.is_file():
            continue
        stored_filename = f"{guideline['id']}{snapshot_path.suffix}"
        shutil.copy2(snapshot_path, guidelines_dir / stored_filename)
        template_guidelines.append(
            {
                "stored_filename": stored_filename,
                "title": guideline.get("title"),
                "scopes": guideline.get("scopes", []),
                "was_default": guideline.get("id") in default_ids,
            }
        )

    manifest = {
        "version": 1,
        "name": name,
        "description": description,
        "project_type": project.get("type"),
        "citation_style": citation.get("style"),
        "custom_citation_style": citation.get("custom_style"),
        "primary_output_type": artefacts.get("primary_output_type"),
        "custom_primary_output_type": artefacts.get("custom_primary_output_type"),
        "source_review_default": sources.get("new_source_status"),
        "prevent_full_document_uploads": privacy.get("do_not_upload_full_documents", True),
        "expects_data_files": data.get("expects_csv_or_sqlite"),
        "guideline_count": len(template_guidelines),
        "guidelines": template_guidelines,
    }
    write_yaml(template_dir / "template.yaml", manifest)
    return template_dir


def init_kwargs_from_template(name: str) -> dict[str, Any]:
    """The subset of `init_workspace`'s keyword arguments a template
    supplies -- merged in by the caller (CLI `init --template`), which still
    wins on any explicitly-passed flag rather than the template silently
    overriding a deliberate choice.
    """
    manifest_path = templates_root() / name / "template.yaml"
    if not manifest_path.is_file():
        raise ValueError(f"Unknown workspace template: {name}")
    manifest = read_yaml(manifest_path)
    kwargs: dict[str, Any] = {}
    for key in (
        "project_type",
        "citation_style",
        "custom_citation_style",
        "primary_output_type",
        "custom_primary_output_type",
        "source_review_default",
        "prevent_full_document_uploads",
        "expects_data_files",
    ):
        value = manifest.get(key)
        if value not in (None, ""):
            kwargs[key] = value
    return kwargs


def apply_template_guidelines(workspace: Path, name: str) -> list[dict[str, Any]]:
    """After `init_workspace` has created `workspace`, copy the template's
    guideline files back in and re-register them via the normal
    `register_guideline` path (so every downstream guideline feature -- style
    detection, conflict reports, AI context -- works exactly as if the user
    had registered them by hand), then restore which ones were marked
    default. Returns the newly registered guideline records.
    """
    template_dir = templates_root() / name
    manifest_path = template_dir / "template.yaml"
    if not manifest_path.is_file():
        raise ValueError(f"Unknown workspace template: {name}")
    manifest = read_yaml(manifest_path)

    registered = []
    default_ids = []
    for entry in manifest.get("guidelines", []):
        stored_path = template_dir / "guidelines" / str(entry.get("stored_filename", ""))
        if not stored_path.is_file():
            continue
        registration = register_guideline(
            workspace, str(stored_path), title=entry.get("title"), scopes=entry.get("scopes") or None
        )
        registered.append(registration.record)
        if entry.get("was_default"):
            default_ids.append(registration.record["id"])

    if default_ids:
        set_default_guidelines(workspace, default_ids)
    return registered
