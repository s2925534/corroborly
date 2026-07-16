import shutil
import subprocess
import sys
import wave
from pathlib import Path
from zipfile import ZipFile

import pytest
from typer.testing import CliRunner

import ledgerly.cli as cli
from ledgerly import __version__
from ledgerly.cli import app
from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.artefacts import register_artefact
from ledgerly.engine.sources import scan_sources, set_source_status
from ledgerly.engine.workspace import init_workspace


runner = CliRunner()


def test_cli_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0, result.output
    assert f"Ledgerly {__version__}" in result.output


def test_cli_doctor_command() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "Ledgerly" in result.output
    assert "is ready" in result.output


def test_cli_zotero_api_link_and_unlink_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    link_result = runner.invoke(
        app,
        [
            "zotero", "api-link",
            "--workspace", str(workspace),
            "--api-key", "super-secret-key",
            "--user-id", "123",
            "--quiet",
        ],
    )
    assert link_result.exit_code == 0, link_result.output
    assert "super-secret-key" not in link_result.output
    env_text = (workspace / ".env").read_text(encoding="utf-8")
    assert "ZOTERO_API_KEY=super-secret-key" in env_text
    assert "ZOTERO_USER_ID=123" in env_text

    unlink_result = runner.invoke(app, ["zotero", "api-unlink", "--workspace", str(workspace), "--quiet"])
    assert unlink_result.exit_code == 0, unlink_result.output
    assert "ZOTERO_API_KEY" not in (workspace / ".env").read_text(encoding="utf-8")


def test_cli_zotero_api_link_rejects_blank_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(
        app,
        ["zotero", "api-link", "--workspace", str(workspace), "--api-key", "", "--user-id", "123", "--quiet"],
    )

    assert result.exit_code == 2, result.output


def test_cli_report_schemas_writes_report_contracts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["report-schemas", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    schemas = read_yaml(workspace / "outputs" / "reports" / "report-schemas.yaml")
    assert "document_validation" in schemas["schemas"]
    assert "citation_insertion_plan" in schemas["schemas"]


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


def test_cli_guidelines_add_and_list(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    guideline = tmp_path / "guideline.md"
    guideline.write_text("# Rules\n\nUse APA7.\n", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    add_result = runner.invoke(
        app,
        [
            "guidelines",
            "add",
            str(guideline),
            "--title",
            "Style Rules",
            "--scope",
            "style",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    list_result = runner.invoke(app, ["guidelines", "list", "--workspace", str(workspace), "--quiet"])

    assert add_result.exit_code == 0, add_result.output
    assert list_result.exit_code == 0, list_result.output
    registry = read_yaml(workspace / "guidelines" / "guidelines.yaml")
    assert registry["guidelines"][0]["title"] == "Style Rules"
    assert registry["guidelines"][0]["scopes"] == ["style"]
    assert Path(registry["guidelines"][0]["snapshot_path"]).is_file()
    assert Path(registry["guidelines"][0]["text_path"]).is_file()


def test_cli_guideline_defaults_are_applied_to_validation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    source_text = workspace / "sources_text" / "source-001.txt"
    guideline = tmp_path / "validation-guideline.md"
    guideline.write_text("# Validation\n\nCheck claim support.\n", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
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
    add_result = runner.invoke(
        app,
        [
            "guidelines",
            "add",
            str(guideline),
            "--scope",
            "validation",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    defaults_result = runner.invoke(
        app,
        ["guidelines", "defaults", "guideline-001", "--workspace", str(workspace), "--quiet"],
    )
    validate_result = runner.invoke(app, ["validate", str(target), "--workspace", str(workspace), "--quiet"])

    assert add_result.exit_code == 0, add_result.output
    assert defaults_result.exit_code == 0, defaults_result.output
    assert validate_result.exit_code == 0, validate_result.output
    report = read_yaml(workspace / "outputs" / "validation" / "document-validation-draft.yaml")
    assert report["guidelines"][0]["id"] == "guideline-001"
    assert report["guidelines"][0]["selection_source"] == "default"


def test_cli_validate_explicit_guidelines_override_defaults(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    first = tmp_path / "default.md"
    second = tmp_path / "explicit.md"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("A short draft.", encoding="utf-8")
    first.write_text("Default validation rules", encoding="utf-8")
    second.write_text("Explicit validation rules", encoding="utf-8")
    runner.invoke(app, ["guidelines", "add", str(first), "--scope", "validation", "--workspace", str(workspace), "--quiet"])
    runner.invoke(app, ["guidelines", "add", str(second), "--scope", "validation", "--workspace", str(workspace), "--quiet"])
    runner.invoke(app, ["guidelines", "defaults", "guideline-001", "--workspace", str(workspace), "--quiet"])

    result = runner.invoke(
        app,
        [
            "validate",
            str(target),
            "--guidelines",
            "guideline-002",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "document-validation-draft.yaml")
    assert [item["id"] for item in report["guidelines"]] == ["guideline-002"]
    assert report["guidelines"][0]["selection_source"] == "explicit"


def test_cli_guidelines_conflicts_writes_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    guideline = tmp_path / "rubric.md"
    guideline.write_text("Use APA 6.", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    add_result = runner.invoke(
        app,
        ["guidelines", "add", str(guideline), "--scope", "rubric", "--workspace", str(workspace), "--quiet"],
    )

    result = runner.invoke(app, ["guidelines", "conflicts", "--workspace", str(workspace), "--quiet"])

    assert add_result.exit_code == 0, add_result.output
    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "guideline-conflicts.yaml")
    assert report["conflict_count"] == 1
    assert report["conflicts"][0]["status"] == "human_review_required"


def test_cli_cite_plan_writes_review_plan(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    source_text = workspace / "sources_text" / "source-001.txt"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
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
                    "citation_metadata": {"authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )

    result = runner.invoke(app, ["cite", "plan", str(target), "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    plan = read_yaml(workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml")
    assert plan["original_document_modified"] is False
    assert plan["insertions"][0]["suggested_inline_citation"] == "(Smith, 2024)"


def test_cli_cite_plan_accepts_citation_style_option(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    source_text = workspace / "sources_text" / "source-001.txt"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
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
                    "citation_metadata": {"authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )

    result = runner.invoke(
        app,
        ["cite", "plan", str(target), "--citation-style", "ieee", "--workspace", str(workspace), "--quiet"],
    )

    assert result.exit_code == 0, result.output
    plan = read_yaml(workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml")
    assert plan["citation_style"] == "ieee"
    assert plan["insertions"][0]["suggested_inline_citation"] == "[1]"


def test_cli_cite_apply_writes_revised_copy(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    source_text = workspace / "sources_text" / "source-001.txt"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
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
                    "citation_metadata": {"authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )
    plan_result = runner.invoke(app, ["cite", "plan", str(target), "--workspace", str(workspace), "--quiet"])
    plan_path = workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml"
    plan = read_yaml(plan_path)
    plan["insertions"][0]["review_status"] = "accepted"
    write_yaml(plan_path, plan)

    apply_result = runner.invoke(app, ["cite", "apply", str(target), "--workspace", str(workspace), "--quiet"])

    assert plan_result.exit_code == 0, plan_result.output
    assert apply_result.exit_code == 0, apply_result.output
    revised = (workspace / "outputs" / "citation-plans" / "citation-applied-draft.md").read_text(encoding="utf-8")
    assert "evidence (Smith, 2024)." in revised
    report = read_yaml(workspace / "outputs" / "citation-plans" / "citation-apply-draft.yaml")
    assert report["applied_insertions"] == 1


def test_cli_cite_review_sets_status_without_hand_editing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    source_text = workspace / "sources_text" / "source-001.txt"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
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
                    "citation_metadata": {"authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )
    runner.invoke(app, ["cite", "plan", str(target), "--workspace", str(workspace), "--quiet"])
    plan_path = workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml"
    insertion = read_yaml(plan_path)["insertions"][0]

    review_result = runner.invoke(
        app,
        [
            "cite",
            "review",
            str(target),
            str(insertion["sentence_index"]),
            insertion["source_id"],
            "accepted",
            "--workspace",
            str(workspace),
        ],
    )
    assert review_result.exit_code == 0, review_result.output
    assert "accepted" in review_result.output
    assert read_yaml(plan_path)["insertions"][0]["review_status"] == "accepted"

    apply_result = runner.invoke(app, ["cite", "apply", str(target), "--workspace", str(workspace), "--quiet"])
    assert apply_result.exit_code == 0, apply_result.output
    report = read_yaml(workspace / "outputs" / "citation-plans" / "citation-apply-draft.yaml")
    assert report["applied_insertions"] == 1


def test_cli_cite_plan_requires_flag_for_candidate_citations(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    explicit_source = tmp_path / "candidate.txt"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")
    explicit_source.write_text("Berth planning evidence supports container terminal automation.", encoding="utf-8")

    blocked_result = runner.invoke(
        app,
        [
            "cite",
            "plan",
            str(target),
            "--source-path",
            str(explicit_source),
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    assert blocked_result.exit_code == 0, blocked_result.output
    blocked = read_yaml(workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml")
    assert blocked["insertions"] == []
    assert blocked["blocked_candidate_citations"]

    allowed_result = runner.invoke(
        app,
        [
            "cite",
            "plan",
            str(target),
            "--source-path",
            str(explicit_source),
            "--allow-candidate-citations",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    assert allowed_result.exit_code == 0, allowed_result.output
    allowed = read_yaml(workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml")
    assert allowed["insertions"][0]["source_id"] == "explicit-source-001"


def test_cli_cite_ai_plan_requires_ai_and_full_target_flags(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target.write_text("Container terminal automation uses berth planning evidence.", encoding="utf-8")

    missing_ai = runner.invoke(
        app,
        ["cite", "ai-plan", str(target), "--full-target-document-ai", "--workspace", str(workspace), "--quiet"],
    )
    missing_target = runner.invoke(app, ["cite", "ai-plan", str(target), "--ai", "--workspace", str(workspace), "--quiet"])

    assert missing_ai.exit_code == 2, missing_ai.output
    assert missing_target.exit_code == 2, missing_target.output


def test_cli_cite_ai_plan_writes_review_plan_without_editing_target(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artefacts" / "papers" / "draft.md"
    source_text = workspace / "sources_text" / "source-001.txt"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    original = "Container terminal automation uses berth planning evidence."
    target.write_text(original, encoding="utf-8")
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
    monkeypatch.setattr(cli, "openai_credentials", lambda _workspace: object())
    monkeypatch.setattr(
        cli,
        "ai_citation_plan_review",
        lambda *_args, **_kwargs: {
            "ai_used": True,
            "requires_user_review": True,
            "original_document_modified": False,
            "recommendations": "AI citation recommendation",
        },
    )

    result = runner.invoke(
        app,
        [
            "cite",
            "ai-plan",
            str(target),
            "--ai",
            "--full-target-document-ai",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )

    assert result.exit_code == 0, result.output
    plan = read_yaml(workspace / "outputs" / "citation-plans" / "citation-plan-draft.yaml")
    assert plan["ai_used"] is True
    assert plan["ai_assistance"]["recommendations"] == "AI citation recommendation"
    assert plan["original_document_modified"] is False
    assert target.read_text(encoding="utf-8") == original


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

    full_file_result = runner.invoke(
        app,
        ["ai", "context-preview", "--full-file-ai", "--workspace", str(workspace), "--quiet"],
    )
    assert full_file_result.exit_code == 2, full_file_result.output


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


def test_cli_ai_usage_log_lists_recorded_calls_without_ai_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    (workspace / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")

    # ai review with no evidence still records an insufficient_evidence entry,
    # and reading the log itself needs no --ai opt-in (it never calls a provider).
    review_result = runner.invoke(app, ["ai", "review", "--ai", "--workspace", str(workspace), "--quiet"])
    assert review_result.exit_code == 0, review_result.output

    result = runner.invoke(app, ["ai", "usage-log", "--workspace", str(workspace)])

    assert result.exit_code == 0, result.output
    # Rich truncates long cell text to fit the test runner's narrow terminal
    # width, so only assert on the stable, short prefix here -- full content
    # correctness is covered directly against list_ai_usage in test_ai.py.
    assert "ai_assist" in result.output
    assert "ai-usage-" in result.output


def test_cli_ai_usage_log_empty_for_fresh_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["ai", "usage-log", "--workspace", str(workspace)])

    assert result.exit_code == 0, result.output


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
    assert (workspace / "outputs" / "validation" / "external-candidate-zotero-matches.yaml").is_file()
    assert (workspace / "outputs" / "validation" / "external-search-evidence-validation.yaml").is_file()
    assert (workspace / "outputs" / "validation" / "external-search-run-comparison.yaml").is_file()


def test_cli_search_import_candidates_writes_pending_metadata_source(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="container port evidence")
    write_yaml(
        workspace / "outputs" / "recommendations" / "external-paper-candidates.yaml",
        {
            "version": 1,
            "candidates": [
                {
                    "candidate_id": "ext-001",
                    "provider": "scopus",
                    "title": "Container port evidence",
                    "year": 2024,
                    "citation_count": 12,
                    "quality_score": 40,
                    "open_access": True,
                    "doi": "10.1000/example",
                    "source_title": "Journal of Ports",
                }
            ],
            "runs": [],
        },
    )

    result = runner.invoke(
        app,
        ["search", "import-candidates", "--candidate-id", "ext-001", "--workspace", str(workspace), "--quiet"],
    )

    assert result.exit_code == 0, result.output
    source_register = read_yaml(workspace / "source-register.yaml")
    assert source_register["sources"][0]["source_id"] == "ext-001"
    assert source_register["sources"][0]["status"] == "pending_review"
    assert source_register["sources"][0]["metadata_only"] is True
    report = read_yaml(workspace / "outputs" / "recommendations" / "external-candidate-import.yaml")
    assert report["imported_count"] == 1


def test_cli_search_scopus_requires_external_search_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["search", "scopus-test", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 2, result.output


def test_cli_search_ai_query_plan_requires_ai_and_external_search_flags(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    missing_ai = runner.invoke(app, ["search", "ai-query-plan", "--external-search", "--workspace", str(workspace), "--quiet"])
    missing_external = runner.invoke(app, ["search", "ai-query-plan", "--ai", "--workspace", str(workspace), "--quiet"])

    assert missing_ai.exit_code == 2, missing_ai.output
    assert missing_external.exit_code == 2, missing_external.output


def test_cli_search_ai_query_plan_writes_report_without_running_search(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    monkeypatch.setattr(cli, "openai_credentials", lambda _workspace: object())
    monkeypatch.setattr(
        cli,
        "ai_workspace_report",
        lambda *_args, **kwargs: {
            "version": 1,
            "kind": kwargs["kind"],
            "source_count": 0,
            "status_changes_applied": False,
            "requires_user_review": True,
        },
    )

    result = runner.invoke(
        app,
        ["search", "ai-query-plan", "--ai", "--external-search", "--workspace", str(workspace), "--quiet"],
    )

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "recommendations" / "openai-external-query-plan.yaml")
    assert report["kind"] == "query_generation"
    assert report["status_changes_applied"] is False


def test_cli_search_ai_candidate_review_requires_ai_and_external_search_flags(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    missing_ai = runner.invoke(app, ["search", "ai-candidate-review", "--external-search", "--workspace", str(workspace), "--quiet"])
    missing_external = runner.invoke(app, ["search", "ai-candidate-review", "--ai", "--workspace", str(workspace), "--quiet"])

    assert missing_ai.exit_code == 2, missing_ai.output
    assert missing_external.exit_code == 2, missing_external.output


def test_cli_search_ai_candidate_review_writes_metadata_first_report(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    monkeypatch.setattr(cli, "openai_credentials", lambda _workspace: object())
    monkeypatch.setattr(
        cli,
        "ai_workspace_report",
        lambda *_args, **kwargs: {
            "version": 1,
            "kind": kwargs["kind"],
            "source_count": 0,
            "status_changes_applied": False,
            "requires_user_review": True,
        },
    )

    result = runner.invoke(
        app,
        ["search", "ai-candidate-review", "--ai", "--external-search", "--workspace", str(workspace), "--quiet"],
    )

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "openai-candidate-validation.yaml")
    assert report["kind"] == "candidate_validation"
    assert report["full_text_mode"] == "metadata_and_abstracts_only"
    assert report["status_changes_applied"] is False


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


def test_cli_export_corpus_writes_combined_accepted_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    source_text = workspace / "sources_text" / "source-001.txt"
    source_text.write_text("Accepted converted source text.", encoding="utf-8")
    write_yaml(workspace / "accepted-sources.yaml", {"version": 1, "source_ids": ["source-001"]})
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "file_name": "paper.txt",
                    "conversion": {"status": "converted", "output_path": str(source_text)},
                }
            ],
        },
    )

    result = runner.invoke(app, ["export-corpus", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    assert (workspace / "outputs" / "reports" / "accepted-source-corpus.txt").is_file()
    manifest = read_yaml(workspace / "outputs" / "reports" / "accepted-source-corpus-manifest.yaml")
    assert manifest["included_count"] == 1


def test_cli_merge_pdfs_writes_dry_run_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    pdf = source_root / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    write_yaml(workspace / "accepted-sources.yaml", {"version": 1, "source_ids": ["source-001"]})
    write_yaml(
        workspace / "source-register.yaml",
        {"version": 1, "sources": [{"source_id": "source-001", "file_name": pdf.name, "file_path": str(pdf)}]},
    )

    result = runner.invoke(app, ["merge-pdfs", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    manifest = read_yaml(workspace / "outputs" / "reports" / "pdf-merge-manifest.yaml")
    assert manifest["dry_run"] is True
    assert manifest["included_count"] == 1
    assert (workspace / "outputs" / "reports" / "pdf-merge-manifest.csv").is_file()


def test_cli_ocr_readiness_writes_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["ocr-readiness", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "ocr-readiness.yaml")
    assert "ocr_supported_locally" in report


def test_cli_processing_issues_writes_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "file_name": "scan.pdf",
                    "file_path": str(tmp_path / "scan.pdf"),
                    "conversion": {"status": "failed", "error": "PDF appears to need OCR"},
                }
            ],
        },
    )

    result = runner.invoke(app, ["processing-issues", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "processing-issues.yaml")
    assert report["issues"][0]["issue_kind"] == "ocr_needed"


def test_cli_metadata_filename_suggestions_writes_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "file_name": "paper.pdf",
                    "file_ext": "pdf",
                    "citation_metadata": {"title": "Container Port Evidence", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )

    result = runner.invoke(app, ["metadata", "filename-suggestions", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "recommendations" / "filename-suggestions.yaml")
    assert report["suggestions"][0]["rename_performed"] is False


def test_cli_metadata_sidecars_updates_source_metadata(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source = source_root / "paper.pdf"
    sidecar = source_root / "paper.bib"
    source.write_text("pdf-ish", encoding="utf-8")
    sidecar.write_text("@article{x, title = {Sidecar Paper}, author = {Smith, A.}, year = {2024}}", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    write_yaml(
        workspace / "source-register.yaml",
        {"version": 1, "sources": [{"source_id": "source-001", "file_path": str(source), "file_name": source.name}]},
    )

    result = runner.invoke(app, ["metadata", "sidecars", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    source_record = read_yaml(workspace / "source-register.yaml")["sources"][0]
    assert source_record["citation_metadata"]["title"] == "Sidecar Paper"
    assert (workspace / "sources_metadata" / "sidecar-metadata.yaml").is_file()


def test_cli_guidelines_ai_context_requires_ai_and_defaults_to_excerpts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    guideline = tmp_path / "rules.md"
    guideline.write_text("A" * 20, encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    runner.invoke(app, ["guidelines", "add", str(guideline), "--workspace", str(workspace), "--quiet"])

    blocked = runner.invoke(app, ["guidelines", "ai-context", "--workspace", str(workspace), "--quiet"])
    allowed = runner.invoke(
        app,
        ["guidelines", "ai-context", "--ai", "--max-excerpt-chars", "5", "--workspace", str(workspace), "--quiet"],
    )

    assert blocked.exit_code == 2, blocked.output
    assert allowed.exit_code == 0, allowed.output
    context = read_yaml(workspace / "outputs" / "validation" / "ai-guideline-context.yaml")
    assert context["guidelines"][0]["text"] == "A" * 5
    assert context["full_guidelines_included"] is False


def test_cli_abstracts_import_writes_candidate_register(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    folder = tmp_path / "abstracts"
    folder.mkdir()
    (folder / "good.txt").write_text("Title: Good\nYear: 2024\nAbstract: Useful abstract.\n", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    result = runner.invoke(app, ["abstracts", "import", str(folder), "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    register = read_yaml(workspace / "outputs" / "recommendations" / "abstract-candidates.yaml")
    assert register["candidate_count"] == 1


def test_cli_ai_workspace_report_commands_require_ai_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    commands = [
        ["ai", "corpus-summary"],
        ["ai", "claim-check"],
        ["ai", "citation-gaps"],
        ["ai", "artefact-cross-reference"],
        ["ai", "source-relevance"],
        ["ai", "abstract-screening"],
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

    result = runner.invoke(
        app,
        ["ai", "context-preview", "--ai", "--full-file-ai", "--directory-ai", "--workspace", str(workspace), "--quiet"],
    )

    assert result.exit_code == 0, result.output
    context = read_yaml(workspace / "outputs" / "validation" / "openai-safe-context.yaml")
    assert context["policy"]["original_files_excluded"] is True
    assert context["sources"][0]["metadata"]["source_id"] == source_id
    assert context["full_file_ai_opt_in"] is True
    assert context["directory_ai_opt_in"] is True


def test_python_module_entrypoint_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ledgerly", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Ledgerly" in result.stdout
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
    assert "ledgerly scan --workspace" in result.output
    assert "scan --workspace <path>" not in result.output
    assert "Useful next commands" in result.output
    assert f"ledgerly config validate --workspace {workspace}" in output
    assert f"ledgerly scan --workspace {workspace} --source /path/to/your/sources" in output
    assert f"ledgerly sources review --workspace {workspace}" in output
    assert f"ledgerly sources status --workspace {workspace}" in output
    assert f"ledgerly sources list --workspace {workspace} --status accepted" in output

    summary_files = list((workspace / "outputs" / "logs" / "run-summaries").glob("*__init.yaml"))
    assert len(summary_files) == 1
    summary = read_yaml(summary_files[0])
    assert summary["next_recommended_action"] == f"Run `ledgerly scan --workspace {workspace}`"


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
    assert f"ledgerly scan --workspace {workspace} --source {source_root}" in output
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


def test_cli_templates_save_list_and_init_with_template(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LEDGERLY_TEMPLATES_ROOT", str(tmp_path / "templates-root"))
    source_workspace = tmp_path / "source-workspace"
    init_workspace(
        source_workspace,
        project_name="Source",
        project_type="PhD",
        topic="",
        citation_style="IEEE",
        primary_output_type="thesis",
        source_review_default="maybe",
        prevent_full_document_uploads=False,
        expects_data_files="yes",
    )
    guideline_path = tmp_path / "style-guide.txt"
    guideline_path.write_text("Follow IEEE citation conventions.", encoding="utf-8")
    from ledgerly.engine.guidelines import register_guideline, set_default_guidelines

    registration = register_guideline(source_workspace, str(guideline_path), title="Style Guide")
    set_default_guidelines(source_workspace, [registration.record["id"]])

    save_result = runner.invoke(
        app, ["templates", "save", "phd-template", "--workspace", str(source_workspace), "--quiet"]
    )
    assert save_result.exit_code == 0, save_result.output

    list_result = runner.invoke(app, ["templates", "list"])
    assert list_result.exit_code == 0, list_result.output
    assert "phd-template" in list_result.output

    new_workspace = tmp_path / "new-workspace"
    init_result = runner.invoke(
        app,
        ["init", str(new_workspace), "--template", "phd-template", "--quiet"],
        input=(
            "Templated Project\n"  # project name (project type skipped, from template)
            "Topic\n"  # topic
            "n\n"  # research questions
            "n\n"  # supervisors
            # citation style, primary output type, expects_data_files, source_review_default
            # all skipped, supplied by the template
            "\n"  # ai preference (default)
            "configure_later\n"  # source location
            "\n"  # artefact root (default)
            "y\n"  # strict evidence mode
            "y\n"  # prevent full document uploads
        ),
    )
    assert init_result.exit_code == 0, init_result.output

    context = read_yaml(new_workspace / "research-context.yaml")
    assert context["project"]["type"] == "PhD"
    assert context["citation"]["style"] == "IEEE"
    assert context["artefacts"]["primary_output_type"] == "thesis"
    assert context["data"]["expects_csv_or_sqlite"] == "yes"
    assert context["sources"]["new_source_status"] == "maybe"

    from ledgerly.engine.guidelines import list_guidelines

    new_guidelines = list_guidelines(new_workspace)
    assert len(new_guidelines) == 1
    assert new_guidelines[0]["title"] == "Style Guide"
    assert Path(new_guidelines[0]["snapshot_path"]).is_file()


def test_cli_templates_save_rejects_invalid_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LEDGERLY_TEMPLATES_ROOT", str(tmp_path / "templates-root"))
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="")

    result = runner.invoke(app, ["templates", "save", "bad name", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 2, result.output


def test_cli_init_with_unknown_template_fails_before_prompting(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LEDGERLY_TEMPLATES_ROOT", str(tmp_path / "templates-root"))
    workspace = tmp_path / "workspace"

    result = runner.invoke(app, ["init", str(workspace), "--template", "does-not-exist", "--quiet"])

    assert result.exit_code == 2, result.output
    assert not workspace.exists() or not (workspace / "research-context.yaml").exists()


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


def test_cli_rqs_wizard_proposes_multiple_candidates_and_saves_kept_ones(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="PhD", topic="")

    inputs = "\n".join(
        [
            "Container terminal automation",  # topic
            "Asian ports",  # scope
            "automation, cost efficiency, and safety",  # relation (3 angles)
            "3",  # question type -> causal
            "Automation improves outcomes",  # hypothesis
            "Automated terminals show statistically better metrics",  # proof
            "No significant difference found",  # disproof
            "y",  # keep candidate 1
            "y",  # keep candidate 2
            "n",  # discard candidate 3
        ]
    ) + "\n"

    result = runner.invoke(app, ["rqs", "wizard", "--workspace", str(workspace)], input=inputs)

    assert result.exit_code == 0, result.output
    assert "Saved 2 draft research question(s): rq-001, rq-002" in result.output
    candidates = read_yaml(workspace / "research-question-candidates.yaml")["candidates"]
    assert [c["id"] for c in candidates] == ["rq-001", "rq-002"]
    assert candidates[0]["question"] == "To what extent does automation in Asian ports?"
    assert candidates[0]["hypothesis"] == "Automation improves outcomes"
    assert candidates[0]["question_type"] == "causal"
    assert candidates[0]["proof_criteria"] == "Automated terminals show statistically better metrics"
    assert candidates[0]["disproof_criteria"] == "No significant difference found"

    # The rest of the RQ workflow works on wizard output exactly like any other RQ.
    approve_result = runner.invoke(app, ["rqs", "approve", "rq-001", "--workspace", str(workspace), "--quiet"])
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


def test_cli_paper_draft_creates_deterministic_skeleton(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test Project",
        project_type="PhD",
        topic="",
        research_questions=[{"question": "A test question?", "status": "draft", "subquestions": []}],
    )

    result = runner.invoke(app, ["paper", "draft", "rq-001", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    draft_path = workspace / "artefacts" / "papers" / "paper-draft-rq-001.md"
    assert draft_path.is_file()
    assert "Status: DRAFT" in draft_path.read_text(encoding="utf-8")
    artefact = read_yaml(workspace / "artefact-registry.yaml")["artefacts"][0]
    assert artefact["type"] == "paper-draft"
    assert artefact["ai_generated"] is False


def test_cli_paper_draft_rejects_unknown_rq_id(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="PhD", topic="")

    result = runner.invoke(app, ["paper", "draft", "rq-999", "--workspace", str(workspace)])

    assert result.exit_code == 2
    assert "Unknown research question" in result.output


def test_cli_transcribe_readiness_reports_unconfigured_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LEDGERLY_SOURCESCRIBE_PATH", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(app, ["transcribe", "readiness", "--workspace", str(workspace)])

    assert result.exit_code == 0, result.output
    assert "Not available" in result.output


def test_cli_transcribe_upload_and_list(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    audio_path = tmp_path / "clip.wav"
    with wave.open(str(audio_path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(8000)
        f.writeframes(b"\x00\x00" * 800)

    upload_result = runner.invoke(app, ["transcribe", "upload", str(audio_path), "--workspace", str(workspace)])
    assert upload_result.exit_code == 0, upload_result.output
    assert "transcribe-001" in upload_result.output

    list_result = runner.invoke(app, ["transcribe", "list", "--workspace", str(workspace)])
    assert list_result.exit_code == 0, list_result.output
    assert "transcribe-001" in list_result.output
    assert "pending" in list_result.output


def test_cli_transcribe_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    bogus_path = tmp_path / "notes.pdf"
    bogus_path.write_text("not audio", encoding="utf-8")

    result = runner.invoke(app, ["transcribe", "upload", str(bogus_path), "--workspace", str(workspace)])

    assert result.exit_code == 2
    assert "Unsupported file extension" in result.output


def test_cli_transcribe_start_fails_without_sourcescribe_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LEDGERLY_SOURCESCRIBE_PATH", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    audio_path = tmp_path / "clip.wav"
    with wave.open(str(audio_path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(8000)
        f.writeframes(b"\x00\x00" * 800)
    runner.invoke(app, ["transcribe", "upload", str(audio_path), "--workspace", str(workspace)])

    result = runner.invoke(app, ["transcribe", "start", "transcribe-001", "--workspace", str(workspace)])

    assert result.exit_code == 2
    assert "LEDGERLY_SOURCESCRIBE_PATH" in result.output


def test_cli_transcribe_status_unknown_job_fails(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(app, ["transcribe", "status", "transcribe-999", "--workspace", str(workspace)])

    assert result.exit_code == 2
    assert "Unknown transcription job_id" in result.output


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


def test_cli_claims_duplicates_writes_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    runner.invoke(app, ["claims", "add", "Automation reduces turnaround time.", "--workspace", str(workspace), "--quiet"])
    runner.invoke(app, ["claims", "add", "Automation reduces turnaround time.", "--workspace", str(workspace), "--quiet"])

    result = runner.invoke(app, ["claims", "duplicates", "--workspace", str(workspace), "--quiet"])

    assert result.exit_code == 0, result.output
    report = read_yaml(workspace / "outputs" / "validation" / "duplicate-claims.yaml")
    assert report["duplicate_pair_count"] == 1


def test_cli_claims_duplicates_rejects_invalid_threshold(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(
        app, ["claims", "duplicates", "--threshold", "1.5", "--workspace", str(workspace), "--quiet"]
    )

    assert result.exit_code == 2, result.output


def test_cli_stages_list_status_target_date_and_ics(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    list_result = runner.invoke(app, ["stages", "list", "--workspace", str(workspace), "--quiet"])
    assert list_result.exit_code == 0, list_result.output
    stage_id = read_yaml(workspace / "research-stages.yaml")["stages"][0]["id"]

    status_result = runner.invoke(
        app, ["stages", "status", stage_id, "in_progress", "--workspace", str(workspace), "--quiet"]
    )
    assert status_result.exit_code == 0, status_result.output
    assert read_yaml(workspace / "research-stages.yaml")["stages"][0]["status"] == "in_progress"

    bad_status_result = runner.invoke(
        app, ["stages", "status", stage_id, "almost_done", "--workspace", str(workspace), "--quiet"]
    )
    assert bad_status_result.exit_code == 2, bad_status_result.output

    date_result = runner.invoke(
        app, ["stages", "target-date", stage_id, "2026-09-30", "--workspace", str(workspace), "--quiet"]
    )
    assert date_result.exit_code == 0, date_result.output
    assert read_yaml(workspace / "research-stages.yaml")["stages"][0]["target_date"] == "2026-09-30"

    ics_result = runner.invoke(app, ["stages", "ics", "--workspace", str(workspace), "--quiet"])
    assert ics_result.exit_code == 0, ics_result.output
    ics_text = (workspace / "outputs" / "reports" / "research-stages.ics").read_text(encoding="utf-8")
    assert "BEGIN:VEVENT" in ics_text
    assert "DTSTART;VALUE=DATE:20260930" in ics_text


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


@pytest.mark.skipif(shutil.which("gpg") is None, reason="No local gpg binary available")
def test_cli_backup_encrypt_and_decrypt_round_trip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    (workspace / "memory.md").write_text("# Memory\nsecret note", encoding="utf-8")

    backup_result = runner.invoke(
        app, ["backup", "--encrypt", "--passphrase", "hunter2", "--workspace", str(workspace), "--quiet"]
    )
    assert backup_result.exit_code == 0, backup_result.output
    encrypted_path = workspace / "outputs" / "backups" / "workspace-backup.zip.gpg"
    assert encrypted_path.is_file()
    assert not (workspace / "outputs" / "backups" / "workspace-backup.zip").exists()

    decrypt_result = runner.invoke(
        app,
        [
            "backup-decrypt",
            str(encrypted_path),
            "--passphrase",
            "hunter2",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    assert decrypt_result.exit_code == 0, decrypt_result.output
    decrypted_path = workspace / "outputs" / "backups" / "workspace-backup.zip"
    assert decrypted_path.is_file()
    with ZipFile(decrypted_path) as zf:
        assert "secret note" in zf.read("memory.md").decode("utf-8")


def test_cli_backup_decrypt_wrong_passphrase_fails(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(
        app,
        [
            "backup-decrypt",
            str(tmp_path / "does-not-exist.zip.gpg"),
            "--passphrase",
            "hunter2",
            "--workspace",
            str(workspace),
            "--quiet",
        ],
    )
    assert result.exit_code == 2, result.output


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
    assert read_yaml(tmp_path / "workspaces" / ".ledgerly-cli.local.yaml") == {
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


def test_cli_doc_version_versions_diff_and_restore(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("line one\n", encoding="utf-8")

    first = runner.invoke(app, ["doc", "version", str(target_path), "--workspace", str(workspace), "--quiet"])
    assert first.exit_code == 0, first.output

    target_path.write_text("line one\nline two\n", encoding="utf-8")
    second = runner.invoke(app, ["doc", "version", str(target_path), "--workspace", str(workspace), "--quiet"])
    assert second.exit_code == 0, second.output

    versions = read_yaml(workspace / "document-vault.yaml")["versions"]
    assert [v["version_id"] for v in versions] == ["docv-001", "docv-002"]

    list_result = runner.invoke(app, ["doc", "versions", str(target_path), "--workspace", str(workspace), "--quiet"])
    assert list_result.exit_code == 0, list_result.output

    diff_result = runner.invoke(
        app, ["doc", "diff", "docv-001", "docv-002", "--workspace", str(workspace), "--quiet"]
    )
    assert diff_result.exit_code == 0, diff_result.output

    restore_result = runner.invoke(
        app, ["doc", "restore", "docv-001", "--workspace", str(workspace), "--quiet"]
    )
    assert restore_result.exit_code == 0, restore_result.output
    restored_versions = read_yaml(workspace / "document-vault.yaml")["versions"]
    assert restored_versions[-1]["creation_reason"] == "restore"
    assert target_path.read_text(encoding="utf-8") == "line one\nline two\n"


def test_cli_doc_compare_reports_not_comparable_without_validation_links(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target_path = workspace / "artefacts" / "notes" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("line one\n", encoding="utf-8")
    runner.invoke(app, ["doc", "version", str(target_path), "--workspace", str(workspace), "--quiet"])
    target_path.write_text("line one\nline two\n", encoding="utf-8")
    runner.invoke(app, ["doc", "version", str(target_path), "--workspace", str(workspace), "--quiet"])

    result = runner.invoke(app, ["doc", "compare", "docv-001", "docv-002", "--workspace", str(workspace)])

    assert result.exit_code == 0, result.output
    assert "Not comparable" in result.output


def test_cli_doc_upload_and_uploads(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    upload_source = tmp_path / "incoming" / "notes.md"
    upload_source.parent.mkdir(parents=True, exist_ok=True)
    upload_source.write_text("# Methodology notes", encoding="utf-8")

    upload_result = runner.invoke(
        app,
        [
            "doc",
            "upload",
            str(upload_source),
            "--title",
            "Methodology Notes",
            "--workspace",
            str(workspace),
        ],
    )
    assert upload_result.exit_code == 0, upload_result.output
    assert "upload-001" in upload_result.output
    assert upload_source.read_text(encoding="utf-8") == "# Methodology notes"  # upload untouched

    uploads_result = runner.invoke(app, ["doc", "uploads", "--workspace", str(workspace), "--quiet"])
    assert uploads_result.exit_code == 0, uploads_result.output

    ledger = read_yaml(workspace / "document-vault.yaml")
    assert ledger["uploads"][0]["upload_id"] == "upload-001"


def test_cli_doc_derive_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")
    target_path = workspace / "artefacts" / "papers" / "draft.md"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("# Intro\n\nContainer automation reduces delays.\n", encoding="utf-8")
    runner.invoke(app, ["doc", "version", str(target_path), "--workspace", str(workspace), "--quiet"])

    result = runner.invoke(app, ["doc", "derive-text", "docv-001", "--workspace", str(workspace)])

    assert result.exit_code == 0, result.output
    assert "Sections: 1" in result.output
    assert "Paragraphs: 1" in result.output
    snapshot_path = workspace / "document_vault" / "derived_text" / "docv-001.yaml"
    assert snapshot_path.is_file()


def test_cli_doc_cross_reference_and_apply(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    artefact_path = workspace / "artefacts" / "transformer-notes.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Transformer Notes\n\nExisting artefact about transformers.\n", encoding="utf-8")
    register_artefact(workspace, title="Transformer Notes", artefact_type="notes", path=artefact_path, linked_sources=[], linked_research_questions=[])

    upload_source = tmp_path / "incoming" / "transformer-findings.md"
    upload_source.parent.mkdir(parents=True, exist_ok=True)
    upload_source.write_text("# Transformer Findings", encoding="utf-8")
    runner.invoke(
        app,
        ["doc", "upload", str(upload_source), "--title", "Transformer Findings", "--workspace", str(workspace)],
    )

    candidates_result = runner.invoke(app, ["doc", "cross-reference", "upload-001", "--workspace", str(workspace)])
    assert candidates_result.exit_code == 0, candidates_result.output
    assert "Candidates: 1" in candidates_result.output
    report_path = workspace / "outputs" / "recommendations" / "cross-reference-upload-001.yaml"
    assert report_path.is_file()

    report = read_yaml(report_path)
    report["candidates"][0]["review_status"] = "accepted"
    write_yaml(report_path, report)

    apply_result = runner.invoke(app, ["doc", "cross-reference-apply", "upload-001", "--workspace", str(workspace)])
    assert apply_result.exit_code == 0, apply_result.output
    assert "Links: 1" in apply_result.output

    ledger = read_yaml(workspace / "document-vault.yaml")
    assert ledger["uploads"][0]["cross_references"][0]["target_kind"] == "artefact"


def test_cli_doc_cross_reference_unknown_upload_id(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(app, ["doc", "cross-reference", "bogus-id", "--workspace", str(workspace)])
    assert result.exit_code == 2

    apply_result = runner.invoke(app, ["doc", "cross-reference-apply", "bogus-id", "--workspace", str(workspace)])
    assert apply_result.exit_code == 2


def test_cli_doc_cross_reference_review_sets_status_without_hand_editing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    artefact_path = workspace / "artefacts" / "transformer-notes.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Transformer Notes\n\nExisting artefact about transformers.\n", encoding="utf-8")
    register_artefact(workspace, title="Transformer Notes", artefact_type="notes", path=artefact_path, linked_sources=[], linked_research_questions=[])

    upload_source = tmp_path / "incoming" / "transformer-findings.md"
    upload_source.parent.mkdir(parents=True, exist_ok=True)
    upload_source.write_text("# Transformer Findings", encoding="utf-8")
    runner.invoke(app, ["doc", "upload", str(upload_source), "--title", "Transformer Findings", "--workspace", str(workspace)])
    runner.invoke(app, ["doc", "cross-reference", "upload-001", "--workspace", str(workspace)])

    report_path = workspace / "outputs" / "recommendations" / "cross-reference-upload-001.yaml"
    candidate = read_yaml(report_path)["candidates"][0]

    review_result = runner.invoke(
        app,
        [
            "doc",
            "cross-reference-review",
            "upload-001",
            candidate["target_kind"],
            candidate["target_id"],
            "accepted",
            "--workspace",
            str(workspace),
        ],
    )
    assert review_result.exit_code == 0, review_result.output
    assert "accepted" in review_result.output

    apply_result = runner.invoke(app, ["doc", "cross-reference-apply", "upload-001", "--workspace", str(workspace)])
    assert "Links: 1" in apply_result.output


def test_cli_doc_cross_reference_review_invalid_status_exits_nonzero(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test Project", project_type="M.Phil", topic="")

    result = runner.invoke(
        app,
        ["doc", "cross-reference-review", "bogus-upload", "artefact", "bogus-id", "accepted", "--workspace", str(workspace)],
    )
    assert result.exit_code == 2
