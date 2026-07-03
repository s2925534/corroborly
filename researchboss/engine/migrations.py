from __future__ import annotations

from pathlib import Path

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.workspace import research_stage_template, zotero_config_for_source


CURRENT_WORKSPACE_SCHEMA_VERSION = 2


def migrate_workspace(workspace: Path) -> list[str]:
    changes: list[str] = []

    context_path = workspace / "research-context.yaml"
    context = read_yaml(context_path)
    sources = context.setdefault("sources", {})
    if "new_source_status" not in sources:
        sources["new_source_status"] = "pending_review"
        changes.append("sources.new_source_status")
    if "requires_manual_review" not in sources:
        sources["requires_manual_review"] = sources.get("new_source_status") == "pending_review"
        changes.append("sources.requires_manual_review")
    if "zotero" not in context:
        context["zotero"] = zotero_config_for_source(sources.get("root"), sources.get("mode", "configure_later"))
        changes.append("zotero")
    write_yaml(context_path, context)

    stages_path = workspace / "research-stages.yaml"
    stages_doc = read_yaml(stages_path)
    if not stages_doc.get("stages"):
        stages = research_stage_template(context.get("project", {}).get("type", ""))
        if stages:
            stages_doc["stages"] = stages
            changes.append("research_stages")
    write_yaml(stages_path, stages_doc)

    state_path = workspace / "research-state.yaml"
    state = read_yaml(state_path)
    if state.get("workspace_schema_version") != CURRENT_WORKSPACE_SCHEMA_VERSION:
        state["workspace_schema_version"] = CURRENT_WORKSPACE_SCHEMA_VERSION
        changes.append("research_state.workspace_schema_version")
    write_yaml(state_path, state)

    return changes
