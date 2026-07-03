import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

import researchboss.cli as cli
from researchboss import __version__
from researchboss.cli import app
from researchboss.core.yamlio import read_yaml, write_yaml
from researchboss.engine.sources import scan_sources, set_source_status
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


def test_cli_validate_writes_document_validation_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "provider": "local_folder",
                    "file_name": "paper.pdf",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                }
            ],
        },
    )

    result = runner.invoke(app, ["validate", str(target), "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "document-validation-draft.yaml")
    assert report["validation_method"] == "deterministic_term_overlap"
    assert report["summary"]["sources_with_overlap"] == 1


def test_cli_ai_test_missing_key_does_not_print_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["ai", "test", "--workspace", str(workspace)])

    assert result.exit_code == 2, result.output
    assert "Missing OPENAI_API_KEY" in result.output
    assert "sk-" not in result.output


def test_cli_ai_test_local_check_writes_report_without_live_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    (workspace / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")

    result = runner.invoke(app, ["ai", "test", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "openai-test.yaml")
    assert report["key_loaded"] is True
    assert report["live_request_performed"] is False
    assert "sk-secret" not in str(report)


def test_cli_ai_context_preview_requires_ai_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["ai", "context-preview", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 2, result.output


def test_cli_ai_review_requires_ai_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["ai", "review", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 2, result.output


def test_cli_assess_novelty_requires_ai_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["assess-novelty", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 2, result.output


def test_cli_rqs_assess_requires_ai_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["rqs", "assess", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 2, result.output


def test_cli_search_plan_writes_query_plan(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="container port evidence")

    result = runner.invoke(app, ["search", "plan", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    assert (workspace / "outputs" / "recommendations" / "external-search-query-plan.yaml").is_file()


def test_cli_search_plan_imports_params_file_and_strategy(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    params = tmp_path / "params.txt"
    params.write_text(
        'Search Parameters - RQ1: Container Readiness\n"container handling" AND "performance metric"\n',
        encoding="utf-8",
    )
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="container port evidence")

    result = runner.invoke(
        app,
        [
            "search",
            "plan",
            "--workspace",
            str(workspace),
            "--params-file",
            str(params),
            "--strategy",
            "strict",
            "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    plan = read_yaml(workspace / "outputs" / "recommendations" / "external-search-query-plan.yaml")
    assert plan["strategy"] == "strict"
    assert plan["imported_query_count"] == 1
    assert plan["query_records"][0]["group_label"] == "RQ1: Container Readiness"


def test_cli_search_refine_plan_writes_saved_plan(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="container port evidence")
    write_yaml(
        workspace / "outputs" / "external-search" / "scopus-no-results.yaml",
        {"version": 1, "queries": [{"query": '"container" AND "port" AND "evidence"'}]},
    )

    result = runner.invoke(app, ["search", "refine-plan", "--workspace", str(workspace), "--max-queries", "1", "--quiet"])

    assert result.exit_code == 0, result.output
    plan = read_yaml(workspace / "outputs" / "recommendations" / "external-search-refine-plan.yaml")
    assert plan["approval_required"] is True
    assert plan["query_count"] == 1


def test_cli_search_reports_writes_external_search_reports(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="container port evidence")
    write_yaml(
        workspace / "outputs" / "recommendations" / "external-paper-candidates.yaml",
        {
            "version": 1,
            "candidates": [
                {
                    "candidate_id": "ext-001",
                    "title": "Container port evidence",
                    "year": 2024,
                    "citation_count": 12,
                    "quality_score": 40,
                    "open_access": True,
                    "doi": "10.1000/example",
                    "eid": "2-s2.0-example",
                }
            ],
            "runs": [{"query": '"container"', "candidate_count": 1, "skipped_count": 0}],
        },
    )

    result = runner.invoke(app, ["search", "reports", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    assert (workspace / "outputs" / "recommendations" / "external-high-signal-candidates.yaml").is_file()
    assert (workspace / "outputs" / "validation" / "external-candidate-duplicates.yaml").is_file()
    assert (workspace / "outputs" / "validation" / "external-search-evidence-validation.yaml").is_file()
    assert (workspace / "outputs" / "validation" / "external-search-run-comparison.yaml").is_file()


def test_cli_search_scopus_requires_external_search_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["search", "scopus-test", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 2, result.output


def test_cli_search_scopus_passes_threshold_options(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    captured = {}

    def fake_credentials(_workspace):
        return object()

    def fake_scopus_search(_workspace, _credentials, *, query, count, thresholds, budgets):
        captured["query"] = query
        captured["count"] = count
        captured["thresholds"] = thresholds
        captured["budgets"] = budgets
        return {
            "metrics": {
                "processed": 1,
                "candidate_count": 1,
                "candidate_register_path": str(workspace / "outputs" / "recommendations" / "external-paper-candidates.yaml"),
                "query_validation_path": str(workspace / "outputs" / "validation" / "external-search-query-validation.yaml"),
            },
            "snapshot_path": str(workspace / "outputs" / "external-search" / "snapshot.json"),
        }

    monkeypatch.setattr(cli, "scopus_credentials", fake_credentials)
    monkeypatch.setattr(cli, "scopus_search", fake_scopus_search)

    result = runner.invoke(
        app,
        [
            "search",
            "scopus",
            '"container"',
            "--workspace",
            str(workspace),
            "--external-search",
            "--count",
            "7",
            "--min-citations",
            "12",
            "--year-from",
            "2020",
            "--year-to",
            "2026",
            "--open-access-only",
            "--low-result-threshold",
            "2",
            "--max-api-calls",
            "1",
            "--max-result-pages",
            "1",
            "--max-results",
            "7",
            "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["query"] == '"container"'
    assert captured["count"] == 7
    assert captured["thresholds"].min_citations == 12
    assert captured["thresholds"].year_from == 2020
    assert captured["thresholds"].year_to == 2026
    assert captured["thresholds"].open_access_only is True
    assert captured["thresholds"].low_result_threshold == 2
    assert captured["budgets"].max_api_calls == 1
    assert captured["budgets"].max_result_pages == 1
    assert captured["budgets"].max_result_count == 7


def test_cli_ai_workspace_report_commands_require_ai_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    commands = [
        ["ai", "corpus-summary"],
        ["ai", "claim-check"],
        ["ai", "citation-gaps"],
        ["ai", "artefact-cross-reference"],
        ["ai", "source-relevance"],
    ]
    for command in commands:
        result = runner.invoke(app, [*command, "--workspace", str(workspace), "--quiet"])
        assert result.exit_code == 2, result.output


def test_cli_ai_context_preview_writes_local_context_without_network(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("excerpt text", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=source_id, new_status="accepted")

    result = runner.invoke(app, ["ai", "context-preview", "--ai", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    context = read_yaml(workspace / "outputs" / "validation" / "openai-safe-context.yaml")
    assert context["policy"]["original_files_excluded"] is True
    assert context["sources"][0]["metadata"]["source_id"] == source_id


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

    migrate_result = runner.invoke(app, ["config", "migrate", "--workspace", str(workspace), "--quiet"])
    assert migrate_result.exit_code == 0, migrate_result.output


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
    assert context["citation"] == {
        "style": "Custom Zotero/CSL style name",
        "custom_style": "Vancouver-like custom style",
    }
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


def test_cli_metadata_extract_updates_source_register(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("Title Line\n2025\nDOI: 10.1234/example", encoding="utf-8")
    init_workspace_with_cli(workspace)
    assert runner.invoke(app, ["scan", "--workspace", str(workspace), "--source", str(source_root), "--quiet"]).exit_code == 0
    assert runner.invoke(app, ["convert", "--workspace", str(workspace), "--quiet"]).exit_code == 0

    result = runner.invoke(app, ["metadata", "extract", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["citation_metadata"]["doi"] == "10.1234/example"
    assert source["citation_metadata"]["year"] == "2025"


def test_cli_metadata_validation_duplicates_and_index(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("Title Line\n2025\nDOI: 10.1234/example", encoding="utf-8")
    init_workspace_with_cli(workspace)
    assert runner.invoke(app, ["scan", "--workspace", str(workspace), "--source", str(source_root), "--quiet"]).exit_code == 0
    assert runner.invoke(app, ["convert", "--workspace", str(workspace), "--quiet"]).exit_code == 0
    assert runner.invoke(app, ["metadata", "extract", "--workspace", str(workspace), "--quiet"]).exit_code == 0

    validate_result = runner.invoke(app, ["metadata", "validate", "--workspace", str(workspace), "--quiet"])
    duplicates_result = runner.invoke(app, ["metadata", "duplicates", "--workspace", str(workspace), "--quiet"])
    index_result = runner.invoke(app, ["metadata", "index", "--workspace", str(workspace), "--quiet"])

    assert validate_result.exit_code == 0, validate_result.output
    assert duplicates_result.exit_code == 0, duplicates_result.output
    assert index_result.exit_code == 0, index_result.output
    assert (workspace / "outputs" / "validation" / "citation-consistency.yaml").is_file()
    assert (workspace / "outputs" / "validation" / "metadata-duplicates.yaml").is_file()
    assert (workspace / "sources_metadata" / "keyword-index.yaml").is_file()


def test_cli_data_profile_profiles_registered_data_sources(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "sample.csv").write_text("name,age\nAda,36\n", encoding="utf-8")
    init_workspace_with_cli(workspace)
    assert runner.invoke(app, ["scan", "--workspace", str(workspace), "--source", str(source_root), "--quiet"]).exit_code == 0

    profile_result = runner.invoke(app, ["data", "profile", "--workspace", str(workspace), "--quiet"])
    list_result = runner.invoke(app, ["data", "list", "--workspace", str(workspace), "--quiet"])
    status_result = runner.invoke(app, ["data", "status", "--workspace", str(workspace), "--quiet"])

    assert profile_result.exit_code == 0, profile_result.output
    assert list_result.exit_code == 0, list_result.output
    assert status_result.exit_code == 0, status_result.output
    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["data_profile"]["status"] == "profiled"
    assert Path(source["data_profile"]["output_path"]).is_file()


def test_cli_rqs_workflow_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="PhD",
        topic="",
        research_questions=[{"question": "Draft?", "status": "draft", "subquestions": []}],
    )

    list_result = runner.invoke(app, ["rqs", "list", "--workspace", str(workspace), "--quiet"])
    approve_result = runner.invoke(app, ["rqs", "approve", "rq-001", "--workspace", str(workspace), "--quiet"])

    assert list_result.exit_code == 0, list_result.output
    assert approve_result.exit_code == 0, approve_result.output
    assert read_yaml(workspace / "research-questions.yaml")["research_questions"][0]["id"] == "rq-001"


def test_cli_rqs_check_writes_readiness_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="PhD",
        topic="",
        research_questions=[{"question": "What is the impact of things?", "status": "draft", "subquestions": []}],
    )

    result = runner.invoke(app, ["rqs", "check", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "research-question-readiness.yaml")
    assert report["ai_used"] is False
    assert report["checked_count"] == 1
    candidates = read_yaml(workspace / "research-question-candidates.yaml")["candidates"]
    assert candidates[0]["readiness"]["checked_by"] == "deterministic_rules"


def test_cli_artefacts_register_and_list(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.write_text("# Summary", encoding="utf-8")

    register_result = runner.invoke(
        app,
        [
            "artefacts",
            "register",
            "Summary",
            "--type",
            "report",
            "--path",
            str(artefact_path),
            "--source",
            "source-001",
            "--rq",
            "rq-001",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    list_result = runner.invoke(app, ["artefacts", "list", "--workspace", str(workspace), "--quiet"])

    assert register_result.exit_code == 0, register_result.output
    assert list_result.exit_code == 0, list_result.output
    artefact = read_yaml(workspace / "artefact-registry.yaml")["artefacts"][0]
    assert artefact["title"] == "Summary"
    assert artefact["linked_sources"] == ["source-001"]
    assert artefact["linked_research_questions"] == ["rq-001"]


def test_cli_artefacts_create_source_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace_with_cli(workspace)
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [{"source_id": "source-001", "status": "accepted", "file_name": "paper.pdf", "file_ext": "pdf"}],
        },
    )

    result = runner.invoke(
        app,
        [
            "artefacts",
            "create",
            "source-summary-report",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (workspace / "artefacts" / "reports" / "source-summary-report.md").is_file()
    artefact = read_yaml(workspace / "artefact-registry.yaml")["artefacts"][0]
    assert artefact["type"] == "source-summary-report"
    assert artefact["ai_generated"] is False


def test_cli_artefact_review_dependencies_health_export_and_backup_inspect(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.write_text("# Summary", encoding="utf-8")
    register_result = runner.invoke(
        app,
        [
            "artefacts",
            "register",
            "Summary",
            "--path",
            str(artefact_path),
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    assert register_result.exit_code == 0, register_result.output

    review_result = runner.invoke(app, ["artefacts", "review", "artefact-001", "accepted", "--workspace", str(workspace), "--quiet"])
    deps_result = runner.invoke(app, ["artefacts", "dependencies", "--workspace", str(workspace), "--quiet"])
    health_result = runner.invoke(app, ["health", "--workspace", str(workspace), "--quiet"])
    export_result = runner.invoke(app, ["export-evidence", "--workspace", str(workspace), "--quiet"])
    backup_result = runner.invoke(app, ["backup", "--workspace", str(workspace), "--quiet"])
    backup_path = workspace / "outputs" / "backups" / f"{workspace.name}-backup.zip"
    inspect_result = runner.invoke(app, ["backup-inspect", str(backup_path), "--workspace", str(workspace), "--quiet"])

    assert review_result.exit_code == 0, review_result.output
    assert deps_result.exit_code == 0, deps_result.output
    assert health_result.exit_code == 0, health_result.output
    assert export_result.exit_code == 0, export_result.output
    assert backup_result.exit_code == 0, backup_result.output
    assert inspect_result.exit_code == 0, inspect_result.output
    assert read_yaml(workspace / "artefact-registry.yaml")["artefacts"][0]["review_status"] == "accepted"
    assert (workspace / "outputs" / "validation" / "artefact-dependencies.yaml").is_file()
    assert (workspace / "outputs" / "reports" / "evidence-bundle.zip").is_file()
    assert (workspace / "outputs" / "validation" / "backup-inspect.yaml").is_file()


def test_cli_zotero_api_select_collections_updates_config(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(
        app,
        [
            "zotero",
            "api-select-collections",
            "ABC",
            "DEF",
            "--no-subcollections",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    zotero_config = read_yaml(workspace / "research-context.yaml")["zotero"]
    assert zotero_config["api_mode"] == "selected_collections"
    assert zotero_config["api_access"] == "read_only"
    assert zotero_config["api_selected_collections"] == [{"key": "ABC"}, {"key": "DEF"}]
    assert zotero_config["api_include_subcollections"] is False


def test_cli_claims_add_list_and_gaps(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    add_result = runner.invoke(app, ["claims", "add", "Unsupported claim", "--workspace", str(workspace), "--quiet"])
    list_result = runner.invoke(app, ["claims", "list", "--workspace", str(workspace), "--quiet"])
    gaps_result = runner.invoke(app, ["claims", "gaps", "--workspace", str(workspace), "--quiet"])

    assert add_result.exit_code == 0, add_result.output
    assert list_result.exit_code == 0, list_result.output
    assert gaps_result.exit_code == 0, gaps_result.output
    assert read_yaml(workspace / "claims-ledger.yaml")["claims"][0]["id"] == "claim-001"
    assert (workspace / "outputs" / "validation" / "citation-gaps.yaml").is_file()


def test_cli_phase4_local_review_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("content", encoding="utf-8")
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    assert runner.invoke(app, ["scan", "--workspace", str(workspace), "--source", str(source_root), "--quiet"]).exit_code == 0
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]

    commands = [
        ["sources", "note", source_id, "Useful source"],
        ["sources", "tag", source_id, "methodology"],
        ["sources", "report"],
        ["claims", "add", "Claim text", "--source", source_id],
        ["claims", "status", "claim-001", "needs_evidence"],
        ["claims", "validate"],
        ["decisions", "add", "Use accepted sources only", "--reason", "Evidence policy"],
        ["terminology", "add", "construct", "A concept being studied"],
        ["feedback", "add", "Narrow scope", "--source", "Supervisor"],
        ["context", "add", "Updated research context"],
        ["timeline"],
    ]
    for command in commands:
        result = runner.invoke(app, [*command, "--workspace", str(workspace), "--quiet"])
        assert result.exit_code == 0, result.output

    source = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source["notes"] == "Useful source"
    assert source["tags"] == ["methodology"]
    assert read_yaml(workspace / "claims-ledger.yaml")["claims"][0]["status"] == "needs_evidence"
    assert (workspace / "outputs" / "validation" / "source-review-report.yaml").is_file()
    assert (workspace / "outputs" / "validation" / "claim-source-validation.yaml").is_file()
    assert (workspace / "outputs" / "reports" / "timeline.yaml").is_file()


def test_cli_report_generates_workspace_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(app, ["report", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    assert (workspace / "outputs" / "reports" / "workspace-report.md").is_file()


def test_cli_watch_writes_candidate_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "new.txt").write_text("new", encoding="utf-8")
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="M.Phil",
        topic="",
        source_root=str(source_root),
        source_mode="local_folder",
    )

    result = runner.invoke(app, ["watch", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    assert (workspace / "outputs" / "recommendations" / "watch-candidates.yaml").is_file()


def test_cli_backup_creates_zip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(app, ["backup", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    assert (workspace / "outputs" / "backups" / "workspace-backup.zip").is_file()


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


def test_cli_zotero_snapshot_blocks_output_inside_zotero_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    storage_root = tmp_path / "Zotero" / "storage"
    storage_root.mkdir(parents=True)
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="M.Phil",
        topic="",
        source_root=str(storage_root),
        source_mode="zotero_storage",
    )
    blocked_output = storage_root.parent / "blocked-snapshot.yaml"

    result = runner.invoke(
        app,
        ["zotero", "snapshot", "--workspace", str(workspace), "--output", str(blocked_output), "--quiet"],
    )

    assert result.exit_code != 0
    assert not blocked_output.exists()
    assert "Blocked write inside local Zotero directory" in str(result.exception)


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
