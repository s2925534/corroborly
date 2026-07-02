from pathlib import Path

from typer.testing import CliRunner

import researchboss.cli as cli
from researchboss.cli import app
from researchboss.core.yamlio import read_yaml


runner = CliRunner()


def init_workspace_with_cli(workspace: Path) -> None:
    result = runner.invoke(
        app,
        ["init", str(workspace), "--quiet"],
        input="Test Project\nM.Phil\nTest topic\nconfigure_later\n\ny\n",
    )
    assert result.exit_code == 0, result.output


def test_cli_init_and_config_validate(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    init_workspace_with_cli(workspace)

    assert (workspace / "research-context.yaml").is_file()
    assert (workspace / "source-register.yaml").is_file()
    assert (workspace / "outputs" / "logs").is_dir()

    result = runner.invoke(app, ["config", "validate", "--workspace", str(workspace), "--quiet"])
    assert result.exit_code == 0, result.output


def test_cli_init_defaults_workspace_under_workspaces_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["init", "--quiet"],
        input="Test Project\nM.Phil\nTest topic\nconfigure_later\n\ny\n",
    )

    assert result.exit_code == 0, result.output
    workspace = tmp_path / "workspaces" / "Test-Project"
    assert (workspace / "research-context.yaml").is_file()
    assert read_yaml(workspace / "research-context.yaml")["project"]["name"] == "Test Project"


def test_cli_init_prints_concrete_scan_next_action(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = runner.invoke(
        app,
        ["init", str(workspace)],
        input="Test Project\nM.Phil\nTest topic\nconfigure_later\n\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert "researchboss scan --workspace" in result.output
    assert "scan --workspace <path>" not in result.output

    summary_files = list((workspace / "outputs" / "logs" / "run-summaries").glob("*__init.yaml"))
    assert len(summary_files) == 1
    summary = read_yaml(summary_files[0])
    assert summary["next_recommended_action"] == f"Run `researchboss scan --workspace {workspace}`"


def test_cli_init_uses_detected_zotero_storage_default(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    zotero_storage = tmp_path / "Zotero" / "storage"
    documents = tmp_path / "Documents"
    zotero_storage.mkdir(parents=True)

    monkeypatch.setattr(cli, "find_default_zotero_storage", lambda: zotero_storage)
    monkeypatch.setattr(cli, "default_documents_dir", lambda: documents)

    result = runner.invoke(
        app,
        ["init", str(workspace), "--quiet"],
        input="Test Project\nM.Phil\nTest topic\n\n\ny\n",
    )
    assert result.exit_code == 0, result.output

    context = read_yaml(workspace / "research-context.yaml")
    assert context["sources"] == {"mode": "zotero_storage", "root": str(zotero_storage)}
    assert context["artefacts"] == {"root": str(documents)}


def test_cli_scan_list_status_and_source_transitions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("content", encoding="utf-8")
    init_workspace_with_cli(workspace)

    scan_result = runner.invoke(
        app,
        ["scan", "--workspace", str(workspace), "--source", str(source_root), "--quiet"],
    )
    assert scan_result.exit_code == 0, scan_result.output

    register = read_yaml(workspace / "source-register.yaml")
    source_id = register["sources"][0]["source_id"]

    list_result = runner.invoke(app, ["sources", "list", "--workspace", str(workspace), "--quiet"])
    assert list_result.exit_code == 0, list_result.output

    status_result = runner.invoke(app, ["sources", "status", "--workspace", str(workspace), "--quiet"])
    assert status_result.exit_code == 0, status_result.output

    accept_result = runner.invoke(app, ["sources", "accept", source_id, "--workspace", str(workspace), "--quiet"])
    assert accept_result.exit_code == 0, accept_result.output
    assert read_yaml(workspace / "accepted-sources.yaml")["source_ids"] == [source_id]

    maybe_result = runner.invoke(app, ["sources", "maybe", source_id, "--workspace", str(workspace), "--quiet"])
    assert maybe_result.exit_code == 0, maybe_result.output
    assert read_yaml(workspace / "maybe-sources.yaml")["source_ids"] == [source_id]

    ignore_result = runner.invoke(
        app,
        ["sources", "ignore", source_id, "--reason", "Out of scope", "--workspace", str(workspace), "--quiet"],
    )
    assert ignore_result.exit_code == 0, ignore_result.output
    assert read_yaml(workspace / "ignored-sources.yaml")["ignored"] == [
        {"source_id": source_id, "reason": "Out of scope"}
    ]
