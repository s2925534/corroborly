from pathlib import Path

from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.migrations import CURRENT_WORKSPACE_SCHEMA_VERSION, migrate_workspace
from researchboss.engine.workspace import init_workspace


def test_migrate_workspace_fills_missing_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    storage = tmp_path / "Zotero" / "storage"
    storage.mkdir(parents=True)
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="PhD",
        topic="",
        source_root=str(storage),
        source_mode="zotero_storage",
    )
    context_path = workspace / "research-context.yaml"
    context = read_yaml(context_path)
    context.pop("zotero")
    context["sources"].pop("new_source_status")
    context["sources"].pop("requires_manual_review")
    write_yaml(context_path, context)
    write_yaml(workspace / "research-stages.yaml", {"version": 1, "stages": []})

    changes = migrate_workspace(workspace)

    migrated_context = read_yaml(context_path)
    assert "zotero" in migrated_context
    assert migrated_context["zotero"]["root"] == str(storage.parent)
    assert migrated_context["sources"]["new_source_status"] == "pending_review"
    assert read_yaml(workspace / "research-stages.yaml")["stages"][1]["name"] == "confirmation"
    assert read_yaml(workspace / "research-state.yaml")["workspace_schema_version"] == CURRENT_WORKSPACE_SCHEMA_VERSION
    assert "zotero" in changes
