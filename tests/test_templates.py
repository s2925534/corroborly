from pathlib import Path

import pytest

from ledgerly.core.yamlio import read_yaml
from ledgerly.engine.guidelines import default_guideline_ids, list_guidelines, register_guideline
from ledgerly.engine.templates import (
    apply_template_guidelines,
    init_kwargs_from_template,
    list_workspace_templates,
    save_workspace_template,
    templates_root,
)
from ledgerly.engine.workspace import init_workspace


@pytest.fixture(autouse=True)
def _isolated_templates_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGERLY_TEMPLATES_ROOT", str(tmp_path / "templates-root"))


def _make_workspace_with_guideline(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test",
        project_type="PhD",
        topic="",
        citation_style="IEEE",
        primary_output_type="thesis",
        source_review_default="maybe",
        prevent_full_document_uploads=False,
        expects_data_files="yes",
    )
    guideline_source = tmp_path / "guideline.txt"
    guideline_source.write_text("Use IEEE citation style throughout.", encoding="utf-8")
    registration = register_guideline(workspace, str(guideline_source), title="Style Guide", scopes=["style"])
    from ledgerly.engine.guidelines import set_default_guidelines

    set_default_guidelines(workspace, [registration.record["id"]])
    return workspace


def test_templates_root_respects_env_override(tmp_path: Path) -> None:
    root = templates_root()
    assert root.is_dir()
    assert str(root).startswith(str(tmp_path))


def test_save_workspace_template_captures_project_config(tmp_path: Path) -> None:
    workspace = _make_workspace_with_guideline(tmp_path)

    template_dir = save_workspace_template(workspace, "phd-template", description="A PhD template")

    manifest = read_yaml(template_dir / "template.yaml")
    assert manifest["name"] == "phd-template"
    assert manifest["project_type"] == "PhD"
    assert manifest["citation_style"] == "IEEE"
    assert manifest["primary_output_type"] == "thesis"
    assert manifest["source_review_default"] == "maybe"
    assert manifest["prevent_full_document_uploads"] is False
    assert manifest["expects_data_files"] == "yes"
    assert manifest["guideline_count"] == 1
    assert manifest["guidelines"][0]["title"] == "Style Guide"
    assert manifest["guidelines"][0]["was_default"] is True
    stored_file = template_dir / "guidelines" / manifest["guidelines"][0]["stored_filename"]
    assert stored_file.is_file()
    assert "IEEE citation style" in stored_file.read_text(encoding="utf-8")


def test_save_workspace_template_rejects_invalid_name(tmp_path: Path) -> None:
    workspace = _make_workspace_with_guideline(tmp_path)
    with pytest.raises(ValueError, match="Template name"):
        save_workspace_template(workspace, "bad name with spaces")


def test_list_workspace_templates_empty_and_populated(tmp_path: Path) -> None:
    assert list_workspace_templates() == []
    workspace = _make_workspace_with_guideline(tmp_path)
    save_workspace_template(workspace, "phd-template")

    templates = list_workspace_templates()
    assert len(templates) == 1
    assert templates[0]["name"] == "phd-template"


def test_init_kwargs_from_template_returns_only_present_fields(tmp_path: Path) -> None:
    workspace = _make_workspace_with_guideline(tmp_path)
    save_workspace_template(workspace, "phd-template")

    kwargs = init_kwargs_from_template("phd-template")

    assert kwargs["project_type"] == "PhD"
    assert kwargs["citation_style"] == "IEEE"
    assert kwargs["source_review_default"] == "maybe"
    assert kwargs["prevent_full_document_uploads"] is False
    assert kwargs["expects_data_files"] == "yes"


def test_init_kwargs_from_template_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown workspace template"):
        init_kwargs_from_template("does-not-exist")


def test_apply_template_guidelines_reregisters_and_restores_default(tmp_path: Path) -> None:
    source_workspace = _make_workspace_with_guideline(tmp_path)
    save_workspace_template(source_workspace, "phd-template")

    new_workspace = tmp_path / "new-workspace"
    init_workspace(new_workspace, project_name="New Test", project_type="PhD", topic="")

    registered = apply_template_guidelines(new_workspace, "phd-template")

    assert len(registered) == 1
    assert registered[0]["title"] == "Style Guide"
    new_guidelines = list_guidelines(new_workspace)
    assert len(new_guidelines) == 1
    assert Path(new_guidelines[0]["snapshot_path"]).is_file()
    assert default_guideline_ids(new_workspace) == [new_guidelines[0]["id"]]


def test_apply_template_guidelines_rejects_unknown_template(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="PhD", topic="")
    with pytest.raises(ValueError, match="Unknown workspace template"):
        apply_template_guidelines(workspace, "does-not-exist")
