import json
from pathlib import Path
from urllib.request import Request

import pytest

from researchboss.core.yamlio import read_yaml
from researchboss.engine.ai import (
    OpenAiCredentials,
    OpenAiError,
    ai_assisted_review,
    ai_novelty_assessment,
    ai_research_question_assessment,
    ai_workspace_report,
    build_safe_context,
    extract_response_text,
    load_dotenv_values,
    openai_post,
    openai_credentials,
    openai_readiness,
    require_ai_flag,
)
from researchboss.engine.conversion import convert_sources
from researchboss.engine.sources import scan_sources, set_source_status
from researchboss.engine.workspace import init_workspace


class FakeResponse:
    def __init__(self, data: object):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.data


def test_load_dotenv_values_reads_openai_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")

    values = load_dotenv_values(env_path)

    assert values["OPENAI_API_KEY"] == "sk-test"


def test_openai_credentials_read_workspace_env_without_exposing_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")

    credentials = openai_credentials(workspace)

    assert credentials.api_key == "sk-secret"


def test_openai_credentials_missing_key_raises_without_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(OpenAiError, match="Missing OPENAI_API_KEY"):
        openai_credentials(tmp_path / "workspace")


def test_require_ai_flag_blocks_ai_actions_without_explicit_opt_in() -> None:
    with pytest.raises(OpenAiError, match="Pass --ai"):
        require_ai_flag(False)


def test_openai_readiness_local_check_does_not_call_network_or_expose_key(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    def opener(_request: Request):
        raise AssertionError("network should not be called")

    report = openai_readiness(
        workspace,
        OpenAiCredentials(api_key="sk-secret"),
        live=False,
        opener=opener,
    )

    assert report["key_loaded"] is True
    assert report["live_request_performed"] is False
    assert report["workspace_ai_enabled"] is False
    assert "sk-secret" not in str(report)


def test_openai_readiness_live_check_uses_bearer_token_without_exposing_key(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    def opener(request: Request):
        assert request.get_method() == "GET"
        assert request.headers["Authorization"] == "Bearer sk-secret"
        return FakeResponse({"data": [{"id": "model-a"}, {"id": "model-b"}]})

    report = openai_readiness(
        workspace,
        OpenAiCredentials(api_key="sk-secret"),
        live=True,
        opener=opener,
    )

    assert report["live_request_performed"] is True
    assert report["api_reachable"] is True
    assert report["model_count"] == 2
    assert "sk-secret" not in str(report)


def test_build_safe_context_uses_accepted_metadata_and_bounded_converted_excerpt(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("A" * 2000, encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    scan_sources(workspace, source_root)
    register_source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=register_source_id, new_status="accepted")
    convert_sources(workspace, status="accepted")

    context = build_safe_context(workspace, max_sources=1, max_excerpt_chars=50)
    source_context = context["sources"][0]

    assert context["policy"]["original_files_excluded"] is True
    assert source_context["metadata"]["source_id"] == register_source_id
    assert "file_path" not in source_context["metadata"]
    assert source_context["original_file_excluded"] is True
    assert source_context["full_document_excluded"] is True
    assert source_context["excerpt"] == "A" * 50
    assert source_context["excerpt_truncated"] is True
    assert str(source_file) not in str(context)


def test_build_safe_context_does_not_include_whole_csv_or_sqlite_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    csv_file = source_root / "data.csv"
    db_file = source_root / "database.sqlite"
    csv_file.write_text("name,value\nsecret,1\n", encoding="utf-8")
    db_file.write_bytes(b"SQLite format 3\x00not a real database")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    scan_sources(workspace, source_root)

    for source in read_yaml(workspace / "source-register.yaml")["sources"]:
        set_source_status(workspace, source_id=source["source_id"], new_status="accepted")

    context = build_safe_context(workspace, max_sources=10, max_excerpt_chars=500)

    assert context["policy"]["whole_csv_excluded"] is True
    assert context["policy"]["whole_sqlite_excluded"] is True
    assert "secret,1" not in str(context)
    assert "not a real database" not in str(context)
    assert all(source["excerpt"] is None for source in context["sources"])


def test_openai_post_uses_responses_api_without_exposing_key() -> None:
    def opener(request: Request):
        assert request.get_method() == "POST"
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == "Bearer sk-secret"
        body = json.loads(request.data.decode("utf-8"))
        assert body == {"model": "gpt-test", "input": "hello"}
        return FakeResponse({"id": "resp_123", "output_text": "ok"})

    data = openai_post(
        "responses",
        OpenAiCredentials(api_key="sk-secret"),
        {"model": "gpt-test", "input": "hello"},
        opener=opener,
    )

    assert extract_response_text(data) == "ok"
    assert "sk-secret" not in str(data)


def test_extract_response_text_supports_output_content_shape() -> None:
    data = {"output": [{"content": [{"type": "output_text", "text": "first"}, {"text": "second"}]}]}

    assert extract_response_text(data) == "first\nsecond"


def test_ai_assisted_review_uses_safe_context_and_requires_human_review(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("bounded evidence text", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=source_id, new_status="accepted")
    convert_sources(workspace, status="accepted")

    def opener(request: Request):
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "gpt-4o-mini"
        assert "bounded evidence text" in body["input"]
        assert str(source_file) not in body["input"]
        return FakeResponse({"id": "resp_review", "output_text": "Review result"})

    report = ai_assisted_review(
        workspace,
        OpenAiCredentials(api_key="sk-secret"),
        max_sources=1,
        max_excerpt_chars=100,
        opener=opener,
    )

    assert report["kind"] == "ai_assisted_review"
    assert report["ai_used"] is True
    assert report["requires_user_review"] is True
    assert report["review"] == "Review result"
    assert "sk-secret" not in str(report)


def test_ai_novelty_assessment_writes_ledger_without_claiming_proof(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("bounded novelty context", encoding="utf-8")
    init_workspace(
        workspace,
        project_name="Test",
        project_type="M.Phil",
        topic="Topic",
        research_questions=[{"question": "How does local evidence tracking affect review quality?", "status": "approved"}],
    )
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=source_id, new_status="accepted")
    convert_sources(workspace, status="accepted")

    def opener(request: Request):
        body = json.loads(request.data.decode("utf-8"))
        assert "How does local evidence tracking affect review quality?" in body["input"]
        assert "bounded novelty context" in body["input"]
        assert str(source_file) not in body["input"]
        return FakeResponse({"id": "resp_novelty", "output_text": "Novelty assessment"})

    report = ai_novelty_assessment(
        workspace,
        OpenAiCredentials(api_key="sk-secret"),
        max_sources=1,
        max_excerpt_chars=100,
        opener=opener,
    )

    ledger = read_yaml(workspace / "novelty-ledger.yaml")
    assert report["kind"] == "ai_assisted_novelty_assessment"
    assert report["requires_user_review"] is True
    assert report["novelty_not_proven"] is True
    assert report["assessment"] == "Novelty assessment"
    assert ledger["assessments"][0]["id"] == "novelty-001"
    assert ledger["assessments"][0]["novelty_not_proven"] is True
    assert "sk-secret" not in str(report)


def test_ai_research_question_assessment_can_target_one_question(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("bounded RQ context", encoding="utf-8")
    init_workspace(
        workspace,
        project_name="Test",
        project_type="M.Phil",
        topic="Topic",
        research_questions=[
            {"question": "How does local evidence tracking affect review quality?", "status": "approved"},
            {"question": "What should be archived?", "status": "draft"},
        ],
    )
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=source_id, new_status="accepted")
    convert_sources(workspace, status="accepted")

    def opener(request: Request):
        body = json.loads(request.data.decode("utf-8"))
        assert "rq-001" in body["input"]
        assert "rq-002" not in body["input"]
        assert "bounded RQ context" in body["input"]
        assert str(source_file) not in body["input"]
        return FakeResponse({"id": "resp_rq", "output_text": "RQ assessment"})

    report = ai_research_question_assessment(
        workspace,
        OpenAiCredentials(api_key="sk-secret"),
        rq_id="rq-001",
        max_sources=1,
        max_excerpt_chars=100,
        opener=opener,
    )

    assert report["kind"] == "ai_research_question_assessment"
    assert report["requires_user_review"] is True
    assert report["novelty_not_proven"] is True
    assert report["research_question_count"] == 1
    assert report["assessment"] == "RQ assessment"


def test_ai_research_question_assessment_rejects_unknown_question(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    with pytest.raises(OpenAiError, match="Unknown research question"):
        ai_research_question_assessment(workspace, OpenAiCredentials(api_key="sk-secret"), rq_id="rq-missing")


def test_ai_workspace_report_uses_safe_context_and_does_not_change_statuses(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    source_file = source_root / "paper.txt"
    source_file.write_text("bounded report context", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    set_source_status(workspace, source_id=source_id, new_status="accepted")
    convert_sources(workspace, status="accepted")

    def opener(request: Request):
        body = json.loads(request.data.decode("utf-8"))
        assert "bounded report context" in body["input"]
        assert str(source_file) not in body["input"]
        assert "do not modify statuses" in body["input"].lower()
        return FakeResponse({"id": "resp_report", "output_text": "Corpus summary"})

    report = ai_workspace_report(
        workspace,
        OpenAiCredentials(api_key="sk-secret"),
        kind="corpus_summary",
        max_sources=1,
        max_excerpt_chars=100,
        opener=opener,
    )

    assert report["kind"] == "corpus_summary"
    assert report["status_changes_applied"] is False
    assert report["requires_user_review"] is True
    assert report["report"] == "Corpus summary"
    assert read_yaml(workspace / "source-register.yaml")["sources"][0]["status"] == "accepted"


def test_ai_workspace_report_rejects_unknown_kind(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    with pytest.raises(OpenAiError, match="Invalid AI workspace report kind"):
        ai_workspace_report(workspace, OpenAiCredentials(api_key="sk-secret"), kind="unknown")
