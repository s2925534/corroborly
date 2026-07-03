import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

import researchboss.cli as cli
from researchboss import __version__
from researchboss.cli import app
from researchboss.core.yamlio import read_yaml
from researchboss.engine.workspace import init_workspace


runner = CliRunner()


def test_cli_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0, result.output
    assert f"ResearchBoss {__version__}" in result.output


def test_cli_doctor_command() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "ResearchBoss" in result.output
    assert "is ready" in result.output


def test_python_module_entrypoint_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "researchboss", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "ResearchBoss" in result.stdout
    assert "init" in result.stdout


def init_workspace_with_cli(workspace: Path) -> None:
    result = runner.invoke(
        app,
        ["init", str(workspace), "--quiet"],
        input="Test Project\n1\nTest topic\nn\nn\n\n\n\n\n\nconfigure_later\n\ny\ny\n",
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
        input="Test Project\n1\nTest topic\nn\nn\n\n\n\n\n\nconfigure_later\n\ny\ny\ny\n",
    )

    assert result.exit_code == 0, result.output
    workspace = tmp_path / "workspaces" / "Test-Project"
    assert (workspace / "research-context.yaml").is_file()
    assert read_yaml(workspace / "research-context.yaml")["project"]["name"] == "Test Project"


def test_cli_init_retries_invalid_numbered_choices(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = runner.invoke(
        app,
        ["init", str(workspace), "--quiet"],
        input="Test Project\nabc\n9\n2\nTest topic\nn\nn\n\n\n\n\n\nconfigure_later\n\ny\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert "Please enter a number from 1 to 5." in result.output
    assert "Invalid value" not in result.output
    assert read_yaml(workspace / "research-context.yaml")["project"]["type"] == "PhD"


def test_cli_init_prints_concrete_scan_next_action(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = runner.invoke(
        app,
        ["init", str(workspace)],
        input="Test Project\n1\nTest topic\nn\nn\n\n\n\n\n\nconfigure_later\n\ny\ny\n",
    )

    assert result.exit_code == 0, result.output
    output = result.output.replace("\n", "")
    assert "researchboss scan --workspace" in result.output
    assert "scan --workspace <path>" not in result.output
    assert "Useful next commands" in result.output
    assert f"researchboss config validate --workspace {workspace}" in output
    assert f"researchboss scan --workspace {workspace} --source /path/to/your/sources" in output
    assert f"researchboss sources review --workspace {workspace}" in output
    assert f"researchboss sources status --workspace {workspace}" in output
    assert f"researchboss sources list --workspace {workspace} --status accepted" in output

    summary_files = list((workspace / "outputs" / "logs" / "run-summaries").glob("*__init.yaml"))
    assert len(summary_files) == 1
    summary = read_yaml(summary_files[0])
    assert summary["next_recommended_action"] == f"Run `researchboss scan --workspace {workspace}`"


def test_cli_init_next_commands_use_configured_source_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()

    result = runner.invoke(
        app,
        ["init", str(workspace)],
        input=(
            "Test Project\n"
            "1\n"
            "Test topic\n"
            "n\n"
            "n\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "\n"
            f"{source_root}\n"
            "\n"
            "y\n"
            "y\n"
        ),
    )

    assert result.exit_code == 0, result.output
    output = result.output.replace("\n", "")
    assert f"researchboss scan --workspace {workspace} --source {source_root}" in output
    assert "/path/to/your/sources" not in result.output


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
        input="Test Project\n1\nTest topic\nn\nn\n\n\n\n\n\n\n\ny\ny\n",
    )
    assert result.exit_code == 0, result.output

    context = read_yaml(workspace / "research-context.yaml")
    assert context["sources"]["mode"] == "zotero_storage"
    assert context["sources"]["root"] == str(zotero_storage)
    assert context["artefacts"]["root"] == str(documents)


def test_cli_init_collects_draft_research_questions_with_subquestions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = runner.invoke(
        app,
        ["init", str(workspace), "--quiet"],
        input=(
            "Test Project\n"
            "2\n"
            "Test topic\n"
            "y\n"
            "How does evidence tracking affect review quality?\n"
            "1\n"
            "y\n"
            "What evidence is retained?\n"
            "How are decisions recorded?\n"
            "\n"
            "n\n"
            "n\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "\n"
            "configure_later\n"
            "\n"
            "y\n"
            "y\n"
        ),
    )

    assert result.exit_code == 0, result.output

    context = read_yaml(workspace / "research-context.yaml")
    assert context["project"]["type"] == "PhD"

    questions = read_yaml(workspace / "research-questions.yaml")
    candidates = read_yaml(workspace / "research-question-candidates.yaml")
    assert questions["research_questions"] == []
    assert candidates["candidates"] == [
        {
            "id": "rq-001",
            "question": "How does evidence tracking affect review quality?",
            "status": "draft",
            "subquestions": ["What evidence is retained?", "How are decisions recorded?"],
        }
    ]


def test_cli_init_collects_setup_preferences(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = runner.invoke(
        app,
        ["init", str(workspace), "--quiet"],
        input=(
            "Test Project\n"
            "4\n"
            "Test topic\n"
            "n\n"
            "y\n"
            "Dr Smith\n"
            "n\n"
            "6\n"
            "Vancouver-like custom style\n"
            "6\n"
            "policy brief\n"
            "1\n"
            "2\n"
            "3\n"
            "configure_later\n"
            "\n"
            "y\n"
            "y\n"
        ),
    )

    assert result.exit_code == 0, result.output

    context = read_yaml(workspace / "research-context.yaml")
    settings = read_yaml(workspace / "app-settings.local.yaml")

    assert context["project"]["type"] == "Industry research"
    assert context["project"]["supervisors_or_stakeholders"] == ["Dr Smith"]
    assert context["citation"] == {"style": "Custom", "custom_style": "Vancouver-like custom style"}
    assert context["artefacts"]["primary_output_type"] == "custom"
    assert context["artefacts"]["custom_primary_output_type"] == "policy brief"
    assert context["data"]["expects_csv_or_sqlite"] == "yes"
    assert context["sources"]["new_source_status"] == "maybe"
    assert context["sources"]["requires_manual_review"] is False
    assert context["privacy"]["do_not_upload_full_documents"] is True
    assert settings["ai"]["enabled"] is False
    assert settings["ai"]["setup_preference"] == "yes but disabled for now"


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


def test_cli_convert_converts_registered_txt_sources(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "notes.txt").write_text("content", encoding="utf-8")
    init_workspace_with_cli(workspace)
    scan_result = runner.invoke(
        app,
        ["scan", "--workspace", str(workspace), "--source", str(source_root), "--quiet"],
    )
    assert scan_result.exit_code == 0, scan_result.output

    convert_result = runner.invoke(app, ["convert", "--workspace", str(workspace), "--quiet"])

    assert convert_result.exit_code == 0, convert_result.output
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["conversion"]["status"] == "converted"
    assert Path(source["conversion"]["output_path"]).is_file()


def test_cli_scan_uses_configured_zotero_provider_when_kind_is_omitted(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    storage_root = tmp_path / "Zotero" / "storage"
    item_dir = storage_root / "ABCD1234"
    item_dir.mkdir(parents=True)
    (item_dir / "Paper.pdf").write_text("pdf-ish", encoding="utf-8")
    (item_dir / ".zotero-ft-cache").write_text("indexed text", encoding="utf-8")
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="M.Phil",
        topic="",
        source_root=str(storage_root),
        source_mode="zotero_storage",
    )

    scan_result = runner.invoke(app, ["scan", "--workspace", str(workspace), "--quiet"])

    assert scan_result.exit_code == 0, scan_result.output
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["provider"] == "zotero_storage"
    assert source["zotero_storage_key"] == "ABCD1234"
    assert source["has_zotero_fulltext_cache"] is True


def test_cli_zotero_search_reads_filename_and_fulltext_cache(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    storage_root = tmp_path / "Zotero" / "storage"
    item_dir = storage_root / "ABCD1234"
    item_dir.mkdir(parents=True)
    (item_dir / "Evidence Synthesis.pdf").write_text("pdf-ish", encoding="utf-8")
    (item_dir / ".zotero-ft-cache").write_text("local first research workspace", encoding="utf-8")
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="M.Phil",
        topic="",
        source_root=str(storage_root),
        source_mode="zotero_storage",
    )

    result = runner.invoke(app, ["zotero", "search", "workspace", "--workspace", str(workspace), "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "Evidence Synthesis.pdf" in result.output
    assert "ABCD1234" in result.output


def test_cli_zotero_test_reports_local_readiness(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    storage_root = tmp_path / "Zotero" / "storage"
    item_dir = storage_root / "ABCD1234"
    item_dir.mkdir(parents=True)
    (item_dir / "Evidence Synthesis.pdf").write_text("pdf-ish", encoding="utf-8")
    (item_dir / ".zotero-ft-cache").write_text("indexed text", encoding="utf-8")
    (storage_root.parent / "zotero.sqlite").write_bytes(b"not sqlite")
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="M.Phil",
        topic="",
        source_root=str(storage_root),
        source_mode="zotero_storage",
    )

    result = runner.invoke(app, ["zotero", "test", "--workspace", str(workspace)])

    assert result.exit_code == 0, result.output
    assert "storage_exists" in result.output
    assert "source_file_count" in result.output
    assert "sqlite_readable" in result.output


def test_cli_commands_prompt_for_workspace_and_remember_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source_root = tmp_path / "source-files"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("content", encoding="utf-8")

    first_workspace = tmp_path / "workspaces" / "First"
    second_workspace = tmp_path / "workspaces" / "Second"
    init_workspace(
        first_workspace,
        project_name="First",
        project_type="M.Phil",
        topic="",
        source_root=str(source_root),
        source_mode="local_folder",
    )
    init_workspace(
        second_workspace,
        project_name="Second",
        project_type="PhD",
        topic="",
        source_root=str(source_root),
        source_mode="local_folder",
    )

    scan_result = runner.invoke(app, ["scan", "--quiet"], input="2\ny\n")

    assert scan_result.exit_code == 0, scan_result.output
    assert "Select workspace" in scan_result.output
    assert "Use this workspace as the default for future commands?" in scan_result.output
    assert read_yaml(tmp_path / "workspaces" / ".researchboss-cli.local.yaml") == {
        "version": 1,
        "default_workspace": str(second_workspace),
    }
    assert len(read_yaml(second_workspace / "source-register.yaml")["sources"]) == 1
    assert read_yaml(first_workspace / "source-register.yaml")["sources"] == []

    status_result = runner.invoke(app, ["sources", "status", "--quiet"], input="\n")

    assert status_result.exit_code == 0, status_result.output
    assert "2. " in status_result.output
    assert "(default)" in status_result.output


def test_cli_commands_auto_select_single_discovered_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "workspaces" / "Only"
    init_workspace(workspace, project_name="Only", project_type="M.Phil", topic="")

    result = runner.invoke(app, ["sources", "status", "--quiet"])

    assert result.exit_code == 0, result.output
    assert "Select workspace" not in result.output
    assert "Use this workspace as the default for future commands?" not in result.output


def test_cli_workspace_prompt_retries_invalid_selection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    first_workspace = tmp_path / "workspaces" / "First"
    second_workspace = tmp_path / "workspaces" / "Second"
    init_workspace(first_workspace, project_name="First", project_type="M.Phil", topic="")
    init_workspace(second_workspace, project_name="Second", project_type="PhD", topic="")

    result = runner.invoke(app, ["sources", "status", "--quiet"], input="abc\n3\n1\nn\n")

    assert result.exit_code == 0, result.output
    assert "Please enter a number from 1 to 2." in result.output
    assert "Invalid value" not in result.output
