import io
import os
import time
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from corroborly.api.app import create_app
from corroborly.api.auth import clear_all_sessions
from corroborly.core.yamlio import read_yaml, write_yaml
from corroborly.engine.sources import scan_sources
from corroborly.engine.workspace import init_workspace
from tests.test_zotero import make_storage, make_zotero_sqlite


TEST_USERNAME = "test-user"
TEST_PASSWORD = "test-password"


@pytest.fixture(autouse=True)
def _reset_sessions():
    clear_all_sessions()
    yield
    clear_all_sessions()


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """An already-authenticated client, for tests that exercise route behavior, not auth itself."""
    monkeypatch.setenv("CORROBORLY_API_USERNAME", TEST_USERNAME)
    monkeypatch.setenv("CORROBORLY_API_PASSWORD", TEST_PASSWORD)
    test_client = TestClient(create_app())
    login_response = test_client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert login_response.status_code == 200, login_response.text
    return test_client


@pytest.fixture()
def unauthenticated_client(monkeypatch) -> TestClient:
    """Username/password configured, but no session established — for testing the auth gate itself."""
    monkeypatch.setenv("CORROBORLY_API_USERNAME", TEST_USERNAME)
    monkeypatch.setenv("CORROBORLY_API_PASSWORD", TEST_PASSWORD)
    return TestClient(create_app())


def test_health_route_has_no_workspace_or_auth_dependency(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_project_status_returns_error_envelope_for_unknown_workspace(client: TestClient, tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    response = client.get("/api/v1/projects/status", params={"workspace": str(missing)})

    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["data"] is None
    assert body["errors"][0]["code"] == "workspace_not_found"


def test_project_status_and_health_use_shared_engine_functions(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    status_response = client.get("/api/v1/projects/status", params={"workspace": str(workspace)})
    health_response = client.get("/api/v1/projects/health", params={"workspace": str(workspace)})

    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["ok"] is True
    assert "accepted" in status_body["data"] or isinstance(status_body["data"], dict)

    assert health_response.status_code == 200
    assert health_response.json()["ok"] is True

    dashboard_response = client.get("/api/v1/projects/dashboard", params={"workspace": str(workspace)})
    assert dashboard_response.status_code == 200
    dashboard_data = dashboard_response.json()["data"]
    assert dashboard_data["artefact_count"] == 0
    assert dashboard_data["open_research_question_count"] == 0
    assert "source_counts" in dashboard_data
    assert "claim_counts" in dashboard_data


def test_project_compare_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    init_workspace(workspace_a, project_name="Project A", project_type="M.Phil", topic="Topic")
    init_workspace(workspace_b, project_name="Project B", project_type="PhD", topic="Topic")

    response = client.get(
        "/api/v1/projects/compare",
        params={"workspaces": [str(workspace_a), str(workspace_b)]},
    )

    assert response.status_code == 200
    rows = response.json()["data"]["workspaces"]
    assert [row["project_name"] for row in rows] == ["Project A", "Project B"]


def test_project_compare_requires_at_least_two_workspaces(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/projects/compare", params={"workspaces": [str(workspace)]})

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "too_few_workspaces"


def test_project_init_creates_workspace_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "new-workspace"

    response = client.post(
        "/api/v1/projects/init",
        json={
            "workspace": str(workspace),
            "project_name": "API Project",
            "project_type": "M.Phil",
            "topic": "API topic",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    context = read_yaml(workspace / "research-context.yaml")
    assert context["project"]["name"] == "API Project"


def test_project_init_rejects_already_initialized_workspace(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/projects/init",
        json={
            "workspace": str(workspace),
            "project_name": "Should not overwrite",
            "project_type": "M.Phil",
            "topic": "",
        },
    )

    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "workspace_already_exists"
    context = read_yaml(workspace / "research-context.yaml")
    assert context["project"]["name"] == "Test"  # original workspace untouched


def test_doc_version_route_never_modifies_the_target_file(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "notes" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    original_text = "line one\n"
    target.write_text(original_text, encoding="utf-8")

    response = client.post(
        "/api/v1/doc/version",
        params={"workspace": str(workspace)},
        json={"target": str(target)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["version_id"] == "docv-001"
    assert target.read_text(encoding="utf-8") == original_text


def test_doc_versions_diff_compare_and_restore_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "notes" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("line one\n", encoding="utf-8")

    first = client.post("/api/v1/doc/version", params={"workspace": str(workspace)}, json={"target": str(target)})
    target.write_text("line one\nline two\n", encoding="utf-8")
    second = client.post("/api/v1/doc/version", params={"workspace": str(workspace)}, json={"target": str(target)})
    assert first.status_code == 200 and second.status_code == 200

    versions = client.get(
        "/api/v1/doc/versions", params={"workspace": str(workspace), "target": str(target)}
    )
    assert versions.status_code == 200
    assert [row["version_id"] for row in versions.json()["data"]] == ["docv-001", "docv-002"]

    diff = client.get(
        "/api/v1/doc/diff",
        params={"workspace": str(workspace), "version_id_a": "docv-001", "version_id_b": "docv-002"},
    )
    assert diff.status_code == 200
    assert diff.json()["data"]["diff_supported"] is True

    compare = client.get(
        "/api/v1/doc/compare",
        params={"workspace": str(workspace), "version_id_a": "docv-001", "version_id_b": "docv-002"},
    )
    assert compare.status_code == 200
    assert compare.json()["data"]["comparable"] is False

    restore = client.post(
        "/api/v1/doc/restore",
        params={"workspace": str(workspace)},
        json={"version_id": "docv-001"},
    )
    assert restore.status_code == 200
    restored_data = restore.json()["data"]
    assert restored_data["restored_from_version_id"] == "docv-001"
    assert Path(restored_data["restored_to_path"]).read_text(encoding="utf-8") == "line one\n"
    assert target.read_text(encoding="utf-8") == "line one\nline two\n"  # current document untouched


def test_doc_ai_edit_session_requires_both_ai_flags(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Intro\n\nSome text here.\n", encoding="utf-8")

    no_ai = client.post(
        "/api/v1/doc/ai-edit-sessions", params={"workspace": str(workspace)}, json={"target": str(target)}
    )
    assert no_ai.status_code == 400
    assert no_ai.json()["errors"][0]["code"] == "ai_not_enabled"

    no_full_target = client.post(
        "/api/v1/doc/ai-edit-sessions",
        params={"workspace": str(workspace)},
        json={"target": str(target), "ai": True},
    )
    assert no_full_target.status_code == 400
    assert no_full_target.json()["errors"][0]["code"] == "full_target_document_ai_not_enabled"


def test_doc_ai_edit_session_full_workflow_via_api(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Intro\n\nContainer terminals require automation.\n", encoding="utf-8")

    _mock_openai(
        monkeypatch,
        "### EDIT paragraph_id=para-001 sentence_id=para-001-sent-01\n"
        "ORIGINAL: Container terminals require automation.\n"
        "PROPOSED: Container terminals require automation to stay competitive.\n"
        "RATIONALE: Clearer wording.\n"
        "### END EDIT\n",
    )

    create_response = client.post(
        "/api/v1/doc/ai-edit-sessions",
        params={"workspace": str(workspace)},
        json={"target": str(target), "ai": True, "full_target_document_ai": True},
    )
    assert create_response.status_code == 200, create_response.text
    session = create_response.json()["data"]
    assert session["edit_count"] == 1
    assert session["original_document_modified"] is False
    session_id = session["session_id"]
    edit_id = session["edits"][0]["edit_id"]

    list_response = client.get("/api/v1/doc/ai-edit-sessions", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    review_response = client.post(
        f"/api/v1/doc/ai-edit-sessions/{session_id}/edits/{edit_id}/review",
        params={"workspace": str(workspace)},
        json={"review_status": "accepted"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["data"]["review_status"] == "accepted"

    apply_response = client.post(
        f"/api/v1/doc/ai-edit-sessions/{session_id}/apply", params={"workspace": str(workspace)}
    )
    assert apply_response.status_code == 200
    report = apply_response.json()["data"]
    assert report["applied_edit_count"] == 1
    assert Path(report["output_path"]).read_text(encoding="utf-8").count("[[AI-EDIT-START]]") == 1
    assert target.read_text(encoding="utf-8") == "# Intro\n\nContainer terminals require automation.\n"


def test_paper_draft_ai_full_review_gate_lifecycle_via_api(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test",
        project_type="PhD",
        topic="",
        research_questions=[{"question": "Does automation improve throughput?", "status": "draft", "subquestions": []}],
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    write_yaml(
        workspace / "source-register.yaml",
        {
            "version": 1,
            "sources": [
                {
                    "source_id": "source-001",
                    "status": "accepted",
                    "file_name": "automation.pdf",
                    "file_ext": "pdf",
                    "citation_metadata": {"title": "Automation Study", "authors": ["A. Smith"], "year": 2020},
                }
            ],
        },
    )
    from corroborly.engine.claims import add_claim

    add_claim(
        workspace,
        text="Automated handling reduced dwell time by 20%.",
        linked_sources=["source-001"],
        linked_research_questions=["rq-001"],
    )

    no_ai = client.post(
        "/api/v1/artefacts/paper-draft/ai", params={"workspace": str(workspace)}, json={"rq_id": "rq-001"}
    )
    assert no_ai.status_code == 400
    assert no_ai.json()["errors"][0]["code"] == "ai_not_enabled"

    create_response = client.post(
        "/api/v1/artefacts/create",
        params={"workspace": str(workspace)},
        json={"artefact_type": "paper-draft", "rq_id": "rq-001"},
    )
    assert create_response.status_code == 200, create_response.text
    skeleton_path = Path(create_response.json()["data"]["path"])

    from corroborly.engine.derived_text import build_derived_text_snapshot
    from corroborly.engine.vault import create_document_version

    version = create_document_version(workspace, str(skeleton_path), creation_reason="test_setup")
    derived = build_derived_text_snapshot(workspace, version["version_id"])
    target_sentence = None
    for paragraph in derived["paragraphs"]:
        for sentence in paragraph["sentences"]:
            if "DRAFT" in sentence["text"]:
                target_sentence = {"paragraph_id": paragraph["paragraph_id"], **sentence}
                break
        if target_sentence:
            break
    assert target_sentence is not None

    _mock_openai(
        monkeypatch,
        f"### EDIT paragraph_id={target_sentence['paragraph_id']} sentence_id={target_sentence['sentence_id']}\n"
        f"ORIGINAL: {target_sentence['text']}\n"
        "PROPOSED: The evidence supports the hypothesis. [[claim:claim-001]]\n"
        "RATIONALE: Grounded in the available claim.\n"
        "### END EDIT\n",
    )

    ai_response = client.post(
        "/api/v1/artefacts/paper-draft/ai",
        params={"workspace": str(workspace)},
        json={"rq_id": "rq-001", "ai": True, "full_target_document_ai": True},
    )
    assert ai_response.status_code == 200, ai_response.text
    session = ai_response.json()["data"]
    session_id = session["session_id"]
    edit_id = session["edits"][0]["edit_id"]

    review_response = client.post(
        f"/api/v1/doc/ai-edit-sessions/{session_id}/edits/{edit_id}/review",
        params={"workspace": str(workspace)},
        json={"review_status": "accepted"},
    )
    assert review_response.status_code == 200

    apply_response = client.post(
        f"/api/v1/doc/ai-edit-sessions/{session_id}/apply", params={"workspace": str(workspace)}
    )
    assert apply_response.status_code == 200

    promote_response = client.post(
        "/api/v1/artefacts/paper-draft/promote",
        params={"workspace": str(workspace)},
        json={"rq_id": "rq-001", "session_id": session_id},
    )
    assert promote_response.status_code == 200, promote_response.text
    assert promote_response.json()["data"]["paper_review_gate"] == "requires_validate"

    gate_before_validate = client.post(
        "/api/v1/artefacts/paper-draft/clear-review-gate", params={"workspace": str(workspace)}, json={"rq_id": "rq-001"}
    )
    assert gate_before_validate.status_code == 400

    from corroborly.engine.doc_validation import validate_document

    validate_document(workspace, str(skeleton_path))

    gate_after_validate = client.post(
        "/api/v1/artefacts/paper-draft/clear-review-gate", params={"workspace": str(workspace)}, json={"rq_id": "rq-001"}
    )
    assert gate_after_validate.status_code == 200, gate_after_validate.text
    assert gate_after_validate.json()["data"]["paper_review_gate"] == "cleared"


def test_doc_ai_edit_session_review_unknown_session_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/doc/ai-edit-sessions/aiedit-999/edits/edit-001/review",
        params={"workspace": str(workspace)},
        json={"review_status": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "invalid_ai_edit_review_status"


def test_doc_diff_unknown_version_returns_404_error_envelope(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get(
        "/api/v1/doc/diff",
        params={"workspace": str(workspace), "version_id_a": "docv-999", "version_id_b": "docv-998"},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "unknown_document_version"


def test_sources_scan_status_note_tag_and_report_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    source_root = tmp_path / "incoming"
    source_root.mkdir()
    (source_root / "paper.pdf").write_bytes(b"%PDF-1.4 fake pdf bytes")

    scan_response = client.post(
        "/api/v1/sources/scan",
        params={"workspace": str(workspace)},
        json={"source_root": str(source_root)},
    )
    assert scan_response.status_code == 200
    assert scan_response.json()["data"]["added"] == 1

    list_response = client.get("/api/v1/sources", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    sources = list_response.json()["data"]
    assert len(sources) == 1
    source_id = sources[0]["source_id"]

    status_response = client.post(
        f"/api/v1/sources/{source_id}/status",
        params={"workspace": str(workspace)},
        json={"new_status": "accepted"},
    )
    assert status_response.status_code == 200

    note_response = client.post(
        f"/api/v1/sources/{source_id}/note",
        params={"workspace": str(workspace)},
        json={"note": "Looks relevant"},
    )
    assert note_response.status_code == 200

    tag_response = client.post(
        f"/api/v1/sources/{source_id}/tags",
        params={"workspace": str(workspace)},
        json={"tag": "core-evidence"},
    )
    assert tag_response.status_code == 200

    report_response = client.get("/api/v1/sources/report", params={"workspace": str(workspace)})
    assert report_response.status_code == 200
    assert report_response.json()["ok"] is True

    updated = client.get("/api/v1/sources", params={"workspace": str(workspace), "status": "accepted"})
    assert updated.status_code == 200
    assert updated.json()["data"][0]["notes"] == "Looks relevant"
    assert "core-evidence" in updated.json()["data"][0]["tags"]


def test_sources_status_unknown_id_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/sources/does-not-exist/status",
        params={"workspace": str(workspace)},
        json={"new_status": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "unknown_source_id"


def test_artefacts_register_review_and_dependencies_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")

    register_response = client.post(
        "/api/v1/artefacts",
        params={"workspace": str(workspace)},
        json={"title": "Summary", "artefact_type": "report", "path": str(artefact_path)},
    )
    assert register_response.status_code == 200
    artefact_id = register_response.json()["data"]["id"]

    list_response = client.get("/api/v1/artefacts", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    review_response = client.post(
        f"/api/v1/artefacts/{artefact_id}/review",
        params={"workspace": str(workspace)},
        json={"status": "accepted"},
    )
    assert review_response.status_code == 200

    dependencies_response = client.get("/api/v1/artefacts/dependencies", params={"workspace": str(workspace)})
    assert dependencies_response.status_code == 200
    assert dependencies_response.json()["ok"] is True


def test_artefacts_review_unknown_id_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/artefacts/does-not-exist/review",
        params={"workspace": str(workspace)},
        json={"status": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "invalid_artefact_review_status"


def test_rqs_list_check_approve_reject_archive_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test",
        project_type="M.Phil",
        topic="Topic",
        research_questions=[
            {"question": "How does X work?", "status": "draft", "subquestions": []},
            {"question": "Should Y be studied?", "status": "draft", "subquestions": []},
        ],
    )

    list_response = client.get("/api/v1/rqs", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    candidates = list_response.json()["data"]["candidates"]
    assert len(candidates) == 2
    first_id = candidates[0]["id"]
    second_id = candidates[1]["id"]

    check_response = client.post(
        "/api/v1/rqs/check", params={"workspace": str(workspace)}, json={}
    )
    assert check_response.status_code == 200

    approve_response = client.post(f"/api/v1/rqs/{first_id}/approve", params={"workspace": str(workspace)})
    assert approve_response.status_code == 200

    reject_response = client.post(
        f"/api/v1/rqs/{second_id}/reject", params={"workspace": str(workspace)}, json={"reason": "Too broad"}
    )
    assert reject_response.status_code == 200

    archive_response = client.post(f"/api/v1/rqs/{first_id}/archive", params={"workspace": str(workspace)}, json={})
    assert archive_response.status_code == 200

    final_response = client.get("/api/v1/rqs", params={"workspace": str(workspace)})
    data = final_response.json()["data"]
    assert data["candidates"] == []
    assert data["approved"] == []


def test_rqs_approve_unknown_id_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post("/api/v1/rqs/rq-999/approve", params={"workspace": str(workspace)})

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "unknown_rq_id"


def test_rqs_wizard_preview_and_save_full_flow_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="PhD", topic="")

    preview_response = client.post(
        "/api/v1/rqs/wizard/preview",
        params={"workspace": str(workspace)},
        json={"scope": "Asian ports", "relation": "automation reduces turnaround time, staffing affects cost", "question_type": "causal"},
    )
    assert preview_response.status_code == 200, preview_response.text
    candidates = preview_response.json()["data"]["candidates"]
    assert len(candidates) == 2
    assert "automation reduces turnaround time" in candidates[0]["question"]
    assert "in Asian ports" in candidates[0]["question"]
    assert "readiness" in candidates[0] and "score" in candidates[0]["readiness"]

    save_response = client.post(
        "/api/v1/rqs/wizard/save",
        params={"workspace": str(workspace)},
        json={
            "question": candidates[0]["question"],
            "hypothesis": "Automation improves outcomes.",
            "question_type": "causal",
            "proof_criteria": "Statistically lower turnaround times.",
            "disproof_criteria": "No significant difference.",
        },
    )
    assert save_response.status_code == 200, save_response.text
    saved = save_response.json()["data"]
    assert saved["question"] == candidates[0]["question"]
    assert saved["hypothesis"] == "Automation improves outcomes."

    list_response = client.get("/api/v1/rqs", params={"workspace": str(workspace)})
    assert len(list_response.json()["data"]["candidates"]) == 1


def test_rqs_wizard_preview_rejects_invalid_question_type(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="PhD", topic="")

    response = client.post(
        "/api/v1/rqs/wizard/preview",
        params={"workspace": str(workspace)},
        json={"relation": "X affects Y", "question_type": "not-a-type"},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_question_type"


def test_conversion_run_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    source_root = tmp_path / "incoming"
    source_root.mkdir()
    (source_root / "notes.txt").write_text("line one\nline two\n", encoding="utf-8")
    scan_sources(workspace, source_root)

    response = client.post("/api/v1/conversion/run", params={"workspace": str(workspace)}, json={})

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["processed"] == 1
    assert body["converted"] == 1
    assert body["results"][0]["status"] == "converted"
    assert (workspace / "sources_text").exists()


def test_metadata_extract_validate_duplicates_index_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    source_root = tmp_path / "incoming"
    source_root.mkdir()
    (source_root / "notes.txt").write_text("DOI: 10.1000/xyz123\n", encoding="utf-8")
    scan_sources(workspace, source_root)
    client.post("/api/v1/conversion/run", params={"workspace": str(workspace)}, json={})

    extract_response = client.post("/api/v1/metadata/extract", params={"workspace": str(workspace)}, json={})
    assert extract_response.status_code == 200
    assert extract_response.json()["data"]["processed"] == 1

    validate_response = client.get("/api/v1/metadata/validate", params={"workspace": str(workspace)})
    assert validate_response.status_code == 200
    assert validate_response.json()["ok"] is True

    duplicates_response = client.get("/api/v1/metadata/duplicates", params={"workspace": str(workspace)})
    assert duplicates_response.status_code == 200
    assert duplicates_response.json()["ok"] is True

    index_response = client.post("/api/v1/metadata/index", params={"workspace": str(workspace)})
    assert index_response.status_code == 200
    assert index_response.json()["ok"] is True


def test_data_profile_list_status_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    source_root = tmp_path / "incoming"
    source_root.mkdir()
    (source_root / "data.csv").write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    scan_sources(workspace, source_root)

    list_response = client.get("/api/v1/data", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    profile_response = client.post("/api/v1/data/profile", params={"workspace": str(workspace)}, json={})
    assert profile_response.status_code == 200
    assert profile_response.json()["data"]["profiled"] == 1

    status_response = client.get("/api/v1/data/status", params={"workspace": str(workspace)})
    assert status_response.status_code == 200
    assert status_response.json()["data"]["profiled"] == 1


def test_claims_add_status_gaps_and_validate_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    add_response = client.post(
        "/api/v1/claims",
        params={"workspace": str(workspace)},
        json={"text": "Container automation reduces turnaround time.", "linked_sources": ["source-001"]},
    )
    assert add_response.status_code == 200
    claim_id = add_response.json()["data"]["id"]

    list_response = client.get("/api/v1/claims", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    status_response = client.post(
        f"/api/v1/claims/{claim_id}/status",
        params={"workspace": str(workspace)},
        json={"status": "needs_evidence"},
    )
    assert status_response.status_code == 200

    gaps_response = client.get("/api/v1/claims/gaps", params={"workspace": str(workspace)})
    assert gaps_response.status_code == 200
    assert gaps_response.json()["ok"] is True

    validate_response = client.get("/api/v1/claims/validate", params={"workspace": str(workspace)})
    assert validate_response.status_code == 200
    assert validate_response.json()["data"]["claims"][0]["issues"][0]["kind"] == "missing_source"

    stale_response = client.get("/api/v1/claims/stale", params={"workspace": str(workspace)})
    assert stale_response.status_code == 200
    stale_data = stale_response.json()["data"]
    assert stale_data["days_threshold"] == 14
    assert stale_data["stale_count"] == 0


def test_claims_duplicates_route_finds_near_identical_pairs(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    client.post(
        "/api/v1/claims", params={"workspace": str(workspace)}, json={"text": "Automation reduces turnaround time."}
    )
    client.post(
        "/api/v1/claims", params={"workspace": str(workspace)}, json={"text": "Automation reduces turnaround time."}
    )

    response = client.get("/api/v1/claims/duplicates", params={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["duplicate_pair_count"] == 1


def test_claims_duplicates_route_rejects_invalid_threshold(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get(
        "/api/v1/claims/duplicates", params={"workspace": str(workspace), "threshold": 1.5}
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_duplicate_threshold"


def test_stages_list_status_target_date_and_ics_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    list_response = client.get("/api/v1/stages", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    stages = list_response.json()["data"]
    assert len(stages) > 0
    stage_id = stages[0]["id"]

    status_response = client.post(
        f"/api/v1/stages/{stage_id}/status",
        params={"workspace": str(workspace)},
        json={"status": "in_progress"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] == "in_progress"

    date_response = client.post(
        f"/api/v1/stages/{stage_id}/target-date",
        params={"workspace": str(workspace)},
        json={"target_date": "2026-09-30"},
    )
    assert date_response.status_code == 200
    assert date_response.json()["data"]["target_date"] == "2026-09-30"

    ics_response = client.get("/api/v1/stages/ics", params={"workspace": str(workspace)})
    assert ics_response.status_code == 200
    assert "BEGIN:VEVENT" in ics_response.text
    assert "DTSTART;VALUE=DATE:20260930" in ics_response.text


def test_stages_status_unknown_stage_id_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/stages/stage-99/status", params={"workspace": str(workspace)}, json={"status": "done"}
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "invalid_stage_status"


def test_stages_status_invalid_value_returns_400(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    stage_id = client.get("/api/v1/stages", params={"workspace": str(workspace)}).json()["data"][0]["id"]

    response = client.post(
        f"/api/v1/stages/{stage_id}/status", params={"workspace": str(workspace)}, json={"status": "almost_done"}
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_stage_status"


def test_stages_target_date_invalid_value_returns_400(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    stage_id = client.get("/api/v1/stages", params={"workspace": str(workspace)}).json()["data"][0]["id"]

    response = client.post(
        f"/api/v1/stages/{stage_id}/target-date",
        params={"workspace": str(workspace)},
        json={"target_date": "not-a-date"},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_stage_target_date"


def test_claims_status_unknown_id_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/claims/does-not-exist/status",
        params={"workspace": str(workspace)},
        json={"status": "needs_evidence"},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "invalid_claim_status"


def test_artefacts_create_deterministic_artefact_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/artefacts/create",
        params={"workspace": str(workspace)},
        json={"artefact_type": "source-summary-report"},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert Path(body["path"]).is_file()
    assert body["record"]["ai_generated"] is False

    conflict_response = client.post(
        "/api/v1/artefacts/create",
        params={"workspace": str(workspace)},
        json={"artefact_type": "source-summary-report"},
    )
    assert conflict_response.status_code == 409


def test_zotero_local_routes_require_configuration(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    collections_response = client.get("/api/v1/zotero/local/collections", params={"workspace": str(workspace)})
    assert collections_response.status_code == 400
    assert collections_response.json()["errors"][0]["code"] == "zotero_not_configured"

    search_response = client.get(
        "/api/v1/zotero/local/search", params={"workspace": str(workspace), "query": "automation"}
    )
    assert search_response.status_code == 400
    assert search_response.json()["errors"][0]["code"] == "zotero_not_configured"


def test_zotero_api_test_fails_without_credentials(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/zotero/api/test", params={"workspace": str(workspace)})

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "zotero_api_error"


def test_zotero_api_save_credentials_links_account_without_echoing_key(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    save_response = client.post(
        "/api/v1/zotero/api/credentials",
        params={"workspace": str(workspace)},
        json={"api_key": "super-secret-key", "user_id": "123"},
    )

    assert save_response.status_code == 200
    body = save_response.json()
    assert body["data"] == {"configured": True}
    assert "super-secret-key" not in save_response.text

    env_text = (workspace / ".env").read_text(encoding="utf-8")
    assert "ZOTERO_API_KEY=super-secret-key" in env_text
    assert "ZOTERO_USER_ID=123" in env_text

    delete_response = client.delete("/api/v1/zotero/api/credentials", params={"workspace": str(workspace)})
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"configured": False}
    assert "ZOTERO_API_KEY" not in (workspace / ".env").read_text(encoding="utf-8")


def test_zotero_api_save_credentials_rejects_blank_fields(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/zotero/api/credentials",
        params={"workspace": str(workspace)},
        json={"api_key": "", "user_id": "123"},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "zotero_credentials_invalid"


def test_zotero_api_select_collections_writes_only_workspace_config(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/zotero/api/collections/select",
        params={"workspace": str(workspace)},
        json={"collection_keys": ["ABC123"], "include_subcollections": False},
    )

    assert response.status_code == 200
    context = read_yaml(workspace / "research-context.yaml")
    assert context["zotero"]["api_selected_collections"] == [{"key": "ABC123"}]
    assert context["zotero"]["api_include_subcollections"] is False
    assert context["zotero"]["api_access"] == "read_only"


def _init_workspace_with_zotero_storage(tmp_path: Path) -> tuple[Path, Path]:
    storage, _first, _second = make_storage(tmp_path)
    zotero_root = storage.parent
    make_zotero_sqlite(zotero_root)
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace, project_name="Test", project_type="M.Phil", topic="Topic", source_root=str(storage)
    )
    return workspace, zotero_root


def test_zotero_local_use_entire_library_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace, _zotero_root = _init_workspace_with_zotero_storage(tmp_path)

    response = client.post("/api/v1/zotero/local/use-entire-library", params={"workspace": str(workspace)})

    assert response.status_code == 200
    context = read_yaml(workspace / "research-context.yaml")
    assert context["zotero"]["mode"] == "entire_library"


def test_zotero_local_select_collections_rejects_unknown_key(client: TestClient, tmp_path: Path) -> None:
    workspace, _zotero_root = _init_workspace_with_zotero_storage(tmp_path)

    response = client.post(
        "/api/v1/zotero/local/collections/select",
        params={"workspace": str(workspace)},
        json={"collection_keys": ["NOPE"], "include_subcollections": True},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "unknown_collection_keys"


def test_zotero_local_select_collections_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace, _zotero_root = _init_workspace_with_zotero_storage(tmp_path)

    response = client.post(
        "/api/v1/zotero/local/collections/select",
        params={"workspace": str(workspace)},
        json={"collection_keys": ["COLLROOT"], "include_subcollections": True},
    )

    assert response.status_code == 200
    context = read_yaml(workspace / "research-context.yaml")
    assert context["zotero"]["mode"] == "selected_collections"
    assert context["zotero"]["selected_collections"][0]["key"] == "COLLROOT"


def test_zotero_local_reports_and_bibtex_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace, _zotero_root = _init_workspace_with_zotero_storage(tmp_path)

    metadata_response = client.get("/api/v1/zotero/local/metadata-report", params={"workspace": str(workspace)})
    assert metadata_response.status_code == 200
    assert metadata_response.json()["data"]["total_attachments"] == 2

    health_response = client.get("/api/v1/zotero/local/attachment-health", params={"workspace": str(workspace)})
    assert health_response.status_code == 200
    assert health_response.json()["data"]["sqlite_attachments"] == 2

    fulltext_response = client.get("/api/v1/zotero/local/fulltext-report", params={"workspace": str(workspace)})
    assert fulltext_response.status_code == 200
    assert fulltext_response.json()["data"]["with_fulltext_cache"] == 1

    duplicates_response = client.get("/api/v1/zotero/local/duplicates", params={"workspace": str(workspace)})
    assert duplicates_response.status_code == 200
    assert len(duplicates_response.json()["data"]["duplicates"]) == 1

    snapshot_response = client.get("/api/v1/zotero/local/snapshot", params={"workspace": str(workspace)})
    assert snapshot_response.status_code == 200
    assert Path(snapshot_response.json()["data"]["snapshot_path"]).is_file()

    bibtex_response = client.get("/api/v1/zotero/local/export-bibtex", params={"workspace": str(workspace)})
    assert bibtex_response.status_code == 200
    bibtex_data = bibtex_response.json()["data"]
    assert bibtex_data["entries"] == 2
    assert Path(bibtex_data["bibtex_path"]).is_file()


def test_reports_workspace_and_timeline_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    workspace_response = client.get("/api/v1/reports/workspace", params={"workspace": str(workspace)})
    assert workspace_response.status_code == 200
    body = workspace_response.json()["data"]
    assert Path(body["report_path"]).is_file()
    assert "Test" in body["markdown"]

    timeline_response = client.get("/api/v1/reports/timeline", params={"workspace": str(workspace)})
    assert timeline_response.status_code == 200
    assert timeline_response.json()["ok"] is True

    relationships_response = client.get("/api/v1/reports/citation-relationships", params={"workspace": str(workspace)})
    assert relationships_response.status_code == 200
    relationships_data = relationships_response.json()["data"]
    assert relationships_data["sources"] == []
    assert relationships_data["claims"] == []
    assert relationships_data["artefacts"] == []

    progress_response = client.get("/api/v1/reports/research-progress", params={"workspace": str(workspace)})
    assert progress_response.status_code == 200
    assert progress_response.json()["data"]["event_count"] == 0


def test_reports_digest_marks_visited_by_default(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    first_response = client.get("/api/v1/reports/digest", params={"workspace": str(workspace)})
    assert first_response.status_code == 200
    assert first_response.json()["data"]["is_first_visit"] is True

    second_response = client.get("/api/v1/reports/digest", params={"workspace": str(workspace)})
    assert second_response.status_code == 200
    assert second_response.json()["data"]["is_first_visit"] is False


def test_reports_digest_mark_seen_false_does_not_update_timestamp(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/reports/digest", params={"workspace": str(workspace), "mark_seen": False})
    assert response.status_code == 200
    assert response.json()["data"]["is_first_visit"] is True

    settings = read_yaml(workspace / "app-settings.local.yaml") if (workspace / "app-settings.local.yaml").exists() else {}
    assert "last_visited_at" not in settings


def test_export_evidence_and_backup_create_inspect_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    export_response = client.post("/api/v1/export/evidence", params={"workspace": str(workspace)})
    assert export_response.status_code == 200
    assert Path(export_response.json()["data"]["bundle_path"]).is_file()

    backup_response = client.post("/api/v1/backup", params={"workspace": str(workspace)}, json={})
    assert backup_response.status_code == 200
    backup_path = backup_response.json()["data"]["backup_path"]
    assert Path(backup_path).is_file()

    inspect_response = client.get("/api/v1/backup/inspect", params={"backup_path": backup_path})
    assert inspect_response.status_code == 200
    assert inspect_response.json()["data"]["contains_original_sources"] is False


def test_export_corpus_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post("/api/v1/export/corpus", params={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert Path(data["manifest_path"]).is_file()
    assert data["included_count"] == 0
    assert data["skipped_count"] == 0


def test_export_supervisor_bundle_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post("/api/v1/export/supervisor-bundle", params={"workspace": str(workspace)})

    assert response.status_code == 200
    bundle_path = Path(response.json()["data"]["bundle_path"])
    assert bundle_path.is_file()
    assert bundle_path.name == "supervisor-bundle.zip"


def test_search_plan_and_reports_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(
        workspace,
        project_name="Test",
        project_type="PhD",
        topic="container port evidence tracking",
        research_questions=[{"question": "How does container tracking affect port review quality?", "status": "approved"}],
    )

    plan_response = client.post(
        "/api/v1/search/plan",
        params={"workspace": str(workspace)},
        json={"max_queries": 5, "strategy": "balanced"},
    )
    assert plan_response.status_code == 200
    plan_data = plan_response.json()["data"]
    assert plan_data["external_search_performed"] is False
    assert plan_data["queries"]

    reports_response = client.get("/api/v1/search/reports", params={"workspace": str(workspace)})
    assert reports_response.status_code == 200
    reports_data = reports_response.json()["data"]
    assert "high_signal" in reports_data
    assert "duplicates" in reports_data
    assert "comparison" in reports_data


def test_search_import_candidates_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    candidate_path = workspace / "outputs" / "recommendations" / "external-paper-candidates.yaml"
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(
        candidate_path,
        {
            "version": 1,
            "candidates": [
                {
                    "candidate_id": "ext-scopus-example",
                    "provider": "scopus",
                    "title": "Container port evidence paper",
                    "year": 2024,
                }
            ],
            "runs": [],
        },
    )

    response = client.post(
        "/api/v1/search/import-candidates",
        params={"workspace": str(workspace)},
        json={"candidate_ids": ["ext-scopus-example"]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["imported_count"] == 1


def test_search_import_candidates_requires_existing_register_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/search/import-candidates",
        params={"workspace": str(workspace)},
        json={"candidate_ids": ["does-not-exist"]},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "search_import_candidates_failed"


def test_abstracts_import_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    abstracts_dir = tmp_path / "legacy-abstracts"
    abstracts_dir.mkdir()
    (abstracts_dir / "paper-1.txt").write_text(
        "Title: Container Port Evidence Tracking\nAuthors: Veloso, P.\nAbstract: A study of port evidence.\n",
        encoding="utf-8",
    )

    response = client.post(
        "/api/v1/abstracts/import",
        params={"workspace": str(workspace)},
        json={"folder": str(abstracts_dir)},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["processed"] == 1
    assert Path(data["register_path"]).is_file()


def test_abstracts_import_rejects_missing_folder_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/abstracts/import",
        params={"workspace": str(workspace)},
        json={"folder": str(tmp_path / "does-not-exist")},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "abstracts_folder_not_found"


def test_notes_add_list_tag_and_search_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    add_response = client.post(
        "/api/v1/notes",
        params={"workspace": str(workspace)},
        json={"text": "Discussed scope with supervisor", "kind": "meeting", "tags": ["scope"]},
    )
    assert add_response.status_code == 200
    note_id = add_response.json()["data"]["id"]

    list_response = client.get("/api/v1/notes", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    tag_response = client.post(
        f"/api/v1/notes/{note_id}/tags", params={"workspace": str(workspace)}, json={"tag": "important"}
    )
    assert tag_response.status_code == 200
    assert "important" in tag_response.json()["data"]["tags"]

    search_response = client.get("/api/v1/notes/search", params={"workspace": str(workspace), "query": "supervisor"})
    assert search_response.status_code == 200
    assert len(search_response.json()["data"]) == 1

    filtered_response = client.get("/api/v1/notes", params={"workspace": str(workspace), "kind": "meeting"})
    assert filtered_response.status_code == 200
    assert len(filtered_response.json()["data"]) == 1


def test_notes_import_transcript_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    vtt_path = tmp_path / "meeting.vtt"
    vtt_path.write_text("WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\nHello.\n", encoding="utf-8")

    response = client.post(
        "/api/v1/notes/import-transcript", params={"workspace": str(workspace)}, json={"path": str(vtt_path)}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["kind"] == "transcript"
    assert data["text"] == "Hello."


def test_notes_import_transcript_missing_file_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/notes/import-transcript",
        params={"workspace": str(workspace)},
        json={"path": str(tmp_path / "missing.vtt")},
    )

    assert response.status_code == 404


def test_export_merge_pdfs_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post("/api/v1/export/merge-pdfs", params={"workspace": str(workspace)}, json={})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dry_run"] is True
    assert Path(data["manifest_path"]).is_file()


def test_conversion_ocr_readiness_and_processing_issues_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    ocr_response = client.get("/api/v1/conversion/ocr-readiness", params={"workspace": str(workspace)})
    assert ocr_response.status_code == 200
    assert "ocr_supported_locally" in ocr_response.json()["data"]

    issues_response = client.get("/api/v1/conversion/processing-issues", params={"workspace": str(workspace)})
    assert issues_response.status_code == 200
    assert issues_response.json()["data"]["issue_count"] == 0


def test_sources_watch_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/sources/watch", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert "candidate_count" in response.json()["data"]


def test_reports_schemas_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/reports/schemas", params={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert Path(data["yaml_path"]).is_file()
    assert data["schema_count"] > 0


def test_backup_inspect_unknown_path_returns_404(client: TestClient, tmp_path: Path) -> None:
    response = client.get("/api/v1/backup/inspect", params={"backup_path": str(tmp_path / "missing.zip")})

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "backup_not_found"


def test_project_log_decisions_terminology_feedback_and_changelog_via_api(
    client: TestClient, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    decision_response = client.post(
        "/api/v1/decisions",
        params={"workspace": str(workspace)},
        json={"text": "Use APA7 citation style.", "reason": "Faculty requirement"},
    )
    assert decision_response.status_code == 200
    assert "Use APA7 citation style." in (workspace / "decisions.md").read_text(encoding="utf-8")

    terminology_response = client.post(
        "/api/v1/terminology",
        params={"workspace": str(workspace)},
        json={"term": "berth", "definition": "A docking location for a vessel."},
    )
    assert terminology_response.status_code == 200

    feedback_response = client.post(
        "/api/v1/feedback",
        params={"workspace": str(workspace)},
        json={"text": "Tighten the literature review scope.", "source": "Supervisor"},
    )
    assert feedback_response.status_code == 200

    changelog_response = client.post(
        "/api/v1/context/changelog",
        params={"workspace": str(workspace)},
        json={"text": "Narrowed research question after supervisor meeting."},
    )
    assert changelog_response.status_code == 200

    assert "berth" in read_yaml(workspace / "terminology.yaml")["terms"][0]["term"]


def test_health_route_requires_no_authentication(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORROBORLY_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_fails_closed_when_auth_not_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORROBORLY_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.get("/api/v1/projects/status", params={"workspace": str(tmp_path)})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "auth_not_configured"


def test_login_fails_closed_when_auth_not_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORROBORLY_API_USERNAME", raising=False)
    monkeypatch.delenv("CORROBORLY_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.post("/api/v1/auth/login", json={"username": "anyone", "password": "anything"})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "auth_not_configured"


def test_login_fails_closed_when_only_password_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORROBORLY_API_USERNAME", raising=False)
    monkeypatch.setenv("CORROBORLY_API_PASSWORD", TEST_PASSWORD)
    bare_client = TestClient(create_app())

    response = bare_client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "auth_not_configured"


def test_login_rejects_wrong_password(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "invalid_credentials"


def test_login_rejects_wrong_username(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": "wrong-user", "password": TEST_PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "invalid_credentials"


def test_protected_route_rejects_request_without_session(unauthenticated_client: TestClient, tmp_path: Path) -> None:
    response = unauthenticated_client.get("/api/v1/projects/status", params={"workspace": str(tmp_path)})

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "unauthorized"


def test_login_success_grants_access_via_cookie(unauthenticated_client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    login_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert login_response.status_code == 200
    assert "token" in login_response.json()["data"]

    status_response = unauthenticated_client.get("/api/v1/projects/status", params={"workspace": str(workspace)})
    assert status_response.status_code == 200


def test_login_remember_me_grants_a_much_longer_session(unauthenticated_client: TestClient) -> None:
    from corroborly.api.auth import DEFAULT_SESSION_TTL_SECONDS, REMEMBER_ME_TTL_SECONDS

    default_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    remembered_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD, "remember": True}
    )

    default_expires = default_response.json()["data"]["expires_at"]
    remembered_expires = remembered_response.json()["data"]["expires_at"]
    now = time.time()

    assert (default_expires - now) < DEFAULT_SESSION_TTL_SECONDS + 5
    assert (remembered_expires - now) > DEFAULT_SESSION_TTL_SECONDS
    assert (remembered_expires - now) < REMEMBER_ME_TTL_SECONDS + 5


def test_change_password_rejects_when_credentials_are_env_vars(client: TestClient) -> None:
    # The `client` fixture configures credentials via monkeypatch.setenv, exactly
    # the case set_credentials must refuse (os.environ always wins over .env, so
    # rewriting .env there would silently have no effect).
    response = client.post(
        "/api/v1/auth/change-password", json={"current_password": TEST_PASSWORD, "new_password": "new-password-123"}
    )
    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "credential_change_failed"


def _dotenv_backed_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.delenv("CORROBORLY_API_USERNAME", raising=False)
    monkeypatch.delenv("CORROBORLY_API_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        f"CORROBORLY_API_USERNAME={TEST_USERNAME}\nCORROBORLY_API_PASSWORD={TEST_PASSWORD}\nOPENAI_API_KEY=\n",
        encoding="utf-8",
    )
    return TestClient(create_app())


def test_change_password_rejects_wrong_current_password(monkeypatch, tmp_path: Path) -> None:
    test_client = _dotenv_backed_client(monkeypatch, tmp_path)
    login_response = test_client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert login_response.status_code == 200

    response = test_client.post(
        "/api/v1/auth/change-password", json={"current_password": "wrong", "new_password": "new-password-123"}
    )
    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "invalid_credentials"


def test_change_password_success_rewrites_env_and_invalidates_all_sessions(monkeypatch, tmp_path: Path) -> None:
    test_client = _dotenv_backed_client(monkeypatch, tmp_path)
    login_response = test_client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    old_token = login_response.json()["data"]["token"]

    change_response = test_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "new-password-123"},
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert change_response.status_code == 200, change_response.text
    assert change_response.json()["data"]["changed"] is True

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "CORROBORLY_API_PASSWORD=new-password-123" in env_text
    assert f"CORROBORLY_API_USERNAME={TEST_USERNAME}" in env_text  # untouched
    assert "OPENAI_API_KEY=" in env_text  # unrelated lines preserved

    # The old session (even the one that made the change) is invalidated.
    stale_response = test_client.get(
        "/api/v1/rqs", params={"workspace": str(tmp_path)}, headers={"Authorization": f"Bearer {old_token}"}
    )
    assert stale_response.status_code == 401

    # Old password no longer works; new password does.
    old_login = test_client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert old_login.status_code == 401
    new_login = test_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": "new-password-123"}
    )
    assert new_login.status_code == 200


def test_login_success_grants_access_via_bearer_token(unauthenticated_client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    login_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    token = login_response.json()["data"]["token"]
    unauthenticated_client.cookies.clear()  # prove the bearer header alone is sufficient

    response = unauthenticated_client.get(
        "/api/v1/projects/status",
        params={"workspace": str(workspace)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_logout_invalidates_session(unauthenticated_client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    login_response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert login_response.status_code == 200

    logout_response = unauthenticated_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    response = unauthenticated_client.get("/api/v1/projects/status", params={"workspace": str(workspace)})
    assert response.status_code == 401


def test_password_is_never_echoed_back_in_login_response(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )

    assert TEST_PASSWORD not in response.text


def test_validation_run_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
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
                    "citation_metadata": {"title": "Accepted Source", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )

    response = client.post(
        "/api/v1/validation/run", params={"workspace": str(workspace)}, json={"target": str(target)}
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert Path(body["yaml_path"]).is_file()
    assert body["report"]["target"]["path"] == str(target)
    assert target.read_text(encoding="utf-8") == "Container terminal automation uses berth planning evidence."


def test_validation_run_unknown_target_returns_400(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/validation/run",
        params={"workspace": str(workspace)},
        json={"target": "does-not-exist.md"},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_validation_target"


def test_citations_plan_and_apply_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    original_text = "Container terminal automation uses berth planning evidence."
    target.write_text(original_text, encoding="utf-8")
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
                    "citation_metadata": {"title": "Accepted Source", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )

    plan_response = client.post(
        "/api/v1/citations/plan", params={"workspace": str(workspace)}, json={"target": str(target)}
    )
    assert plan_response.status_code == 200
    plan_body = plan_response.json()["data"]
    assert target.read_text(encoding="utf-8") == original_text  # plan never edits the original

    plan_path = Path(plan_body["yaml_path"])
    plan_data = read_yaml(plan_path)
    plan_data["insertions"][0]["review_status"] = "accepted"
    write_yaml(plan_path, plan_data)

    apply_response = client.post(
        "/api/v1/citations/apply", params={"workspace": str(workspace)}, json={"target": str(target)}
    )
    assert apply_response.status_code == 200
    apply_body = apply_response.json()["data"]
    assert apply_body["applied"] == 1
    assert "version_id" in apply_body
    assert target.read_text(encoding="utf-8") == original_text  # original still untouched after apply


def test_citations_plan_accepts_citation_style_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
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
                    "citation_metadata": {"title": "Accepted Source", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )

    response = client.post(
        "/api/v1/citations/plan",
        params={"workspace": str(workspace)},
        json={"target": str(target), "citation_style": "mla"},
    )
    assert response.status_code == 200
    plan = response.json()["data"]["plan"]
    assert plan["citation_style"] == "mla"
    assert plan["insertions"][0]["suggested_inline_citation"] == "(Smith)"


def test_citations_plan_rejects_unknown_citation_style_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Some text.", encoding="utf-8")

    response = client.post(
        "/api/v1/citations/plan",
        params={"workspace": str(workspace)},
        json={"target": str(target), "citation_style": "harvard"},
    )
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_citation_style"


def test_citations_ai_plan_requires_both_ai_flags(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Some text.", encoding="utf-8")

    no_ai = client.post(
        "/api/v1/citations/ai-plan", params={"workspace": str(workspace)}, json={"target": str(target)}
    )
    assert no_ai.status_code == 400
    assert no_ai.json()["errors"][0]["code"] == "ai_not_enabled"

    no_full_target = client.post(
        "/api/v1/citations/ai-plan",
        params={"workspace": str(workspace)},
        json={"target": str(target), "ai": True},
    )
    assert no_full_target.status_code == 400
    assert no_full_target.json()["errors"][0]["code"] == "full_target_document_ai_not_enabled"


def test_citations_ai_plan_full_workflow_via_api(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
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
                    "citation_metadata": {"title": "Accepted Source", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )
    _mock_openai(monkeypatch, "Insert a citation after sentence one.")

    response = client.post(
        "/api/v1/citations/ai-plan",
        params={"workspace": str(workspace)},
        json={"target": str(target), "ai": True, "full_target_document_ai": True},
    )

    assert response.status_code == 200, response.text
    plan = response.json()["data"]["plan"]
    assert plan["ai_used"] is True
    assert plan["original_document_modified"] is False
    assert plan["ai_assistance"]["recommendations"] == "Insert a citation after sentence one."
    assert target.read_text(encoding="utf-8") == "Container terminal automation uses berth planning evidence."
    markdown = Path(response.json()["data"]["markdown_path"]).read_text(encoding="utf-8")
    assert "## AI Recommendations" in markdown


def test_citations_plan_insertion_review_sets_status_without_hand_editing_via_api(
    client: TestClient, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
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
                    "citation_metadata": {"title": "Accepted Source", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )
    plan_response = client.post(
        "/api/v1/citations/plan", params={"workspace": str(workspace)}, json={"target": str(target)}
    )
    insertion = plan_response.json()["data"]["plan"]["insertions"][0]

    review_response = client.post(
        "/api/v1/citations/plan/insertion-review",
        params={"workspace": str(workspace)},
        json={
            "target": str(target),
            "sentence_index": insertion["sentence_index"],
            "source_id": insertion["source_id"],
            "review_status": "accepted",
        },
    )

    assert review_response.status_code == 200
    assert review_response.json()["data"]["review_status"] == "accepted"

    apply_response = client.post(
        "/api/v1/citations/apply", params={"workspace": str(workspace)}, json={"target": str(target)}
    )
    assert apply_response.json()["data"]["applied"] == 1


def test_citations_plan_insertion_review_rejects_invalid_status_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
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
                    "citation_metadata": {"title": "Accepted Source", "authors": ["Smith, A."], "year": 2024},
                }
            ],
        },
    )
    client.post("/api/v1/citations/plan", params={"workspace": str(workspace)}, json={"target": str(target)})

    response = client.post(
        "/api/v1/citations/plan/insertion-review",
        params={"workspace": str(workspace)},
        json={"target": str(target), "sentence_index": 0, "source_id": "source-001", "review_status": "maybe-later"},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "citation_insertion_review_failed"


def test_guidelines_register_list_defaults_and_conflicts_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    guideline_file = tmp_path / "style-guide.txt"
    guideline_file.write_text("Use APA 7 citation style throughout.", encoding="utf-8")

    register_response = client.post(
        "/api/v1/guidelines",
        params={"workspace": str(workspace)},
        json={"source": str(guideline_file), "title": "Faculty Style Guide", "scopes": ["citation"]},
    )
    assert register_response.status_code == 200
    guideline_id = register_response.json()["data"]["record"]["id"]

    list_response = client.get("/api/v1/guidelines", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    defaults_response = client.post(
        "/api/v1/guidelines/defaults",
        params={"workspace": str(workspace)},
        json={"guideline_ids": [guideline_id]},
    )
    assert defaults_response.status_code == 200
    assert defaults_response.json()["data"]["default_guideline_ids"] == [guideline_id]

    conflicts_response = client.get("/api/v1/guidelines/conflicts", params={"workspace": str(workspace)})
    assert conflicts_response.status_code == 200
    assert conflicts_response.json()["ok"] is True


def test_guidelines_defaults_rejects_unknown_id(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/guidelines/defaults",
        params={"workspace": str(workspace)},
        json={"guideline_ids": ["guideline-999"]},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_guideline_ids"


def test_db_full_lifecycle_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    init_response = client.post("/api/v1/db/init", params={"workspace": str(workspace)})
    assert init_response.status_code == 200
    assert Path(init_response.json()["data"]["database_path"]).is_file()

    sync_response = client.post("/api/v1/db/sync", params={"workspace": str(workspace)})
    assert sync_response.status_code == 200
    assert sync_response.json()["data"]["report"]["files_synced"] >= 1

    status_response = client.get("/api/v1/db/status", params={"workspace": str(workspace)})
    assert status_response.status_code == 200
    assert status_response.json()["data"]["report"]["status"] == "ok"

    pending_response = client.get("/api/v1/db/pending", params={"workspace": str(workspace)})
    assert pending_response.status_code == 200

    apply_pending_response = client.post(
        "/api/v1/db/apply-pending", params={"workspace": str(workspace)}, json={"apply": False}
    )
    assert apply_pending_response.status_code == 200

    privacy_response = client.get("/api/v1/db/privacy", params={"workspace": str(workspace)})
    assert privacy_response.status_code == 200
    assert privacy_response.json()["data"]["report"]["status"] == "ok"

    rebuild_response = client.post("/api/v1/db/rebuild", params={"workspace": str(workspace)})
    assert rebuild_response.status_code == 200

    search_response = client.get("/api/v1/db/search", params={"workspace": str(workspace), "query": "Test"})
    assert search_response.status_code == 200
    assert search_response.json()["data"]["report"]["status"] == "ok"
    assert rebuild_response.json()["data"]["report"]["status"] == "rebuilt"


def test_resolve_workspace_accepts_relative_path_inside_configured_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "nas-volume"
    root.mkdir()
    workspace = root / "project-a"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("CORROBORLY_WORKSPACE_ROOT", str(root))

    response = client.get("/api/v1/projects/status", params={"workspace": "project-a"})

    assert response.status_code == 200


def test_resolve_workspace_accepts_absolute_path_inside_configured_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "nas-volume"
    root.mkdir()
    workspace = root / "project-a"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("CORROBORLY_WORKSPACE_ROOT", str(root))

    response = client.get("/api/v1/projects/status", params={"workspace": str(workspace)})

    assert response.status_code == 200


def test_resolve_workspace_rejects_path_outside_configured_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "nas-volume"
    root.mkdir()
    outside_workspace = tmp_path / "outside" / "workspace"
    init_workspace(outside_workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("CORROBORLY_WORKSPACE_ROOT", str(root))

    response = client.get("/api/v1/projects/status", params={"workspace": str(outside_workspace)})

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "workspace_outside_root"


def test_resolve_workspace_rejects_traversal_outside_configured_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "nas-volume"
    root.mkdir()
    outside_workspace = tmp_path / "outside" / "workspace"
    init_workspace(outside_workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("CORROBORLY_WORKSPACE_ROOT", str(root))

    response = client.get(
        "/api/v1/projects/status", params={"workspace": "../outside/workspace"}
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "workspace_outside_root"


def test_resolve_workspace_without_configured_root_keeps_local_first_flexibility(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CORROBORLY_WORKSPACE_ROOT", raising=False)
    workspace = tmp_path / "anywhere" / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/projects/status", params={"workspace": str(workspace)})

    assert response.status_code == 200


def test_artefacts_upload_accepts_batch_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[
            ("files", ("notes-one.md", b"# Notes one", "text/markdown")),
            ("files", ("notes-two.md", b"# Notes two", "text/markdown")),
        ],
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["processed"] == 2
    assert body["accepted"] == 2
    assert body["rejected"] == 0
    assert {row["file_name"] for row in body["rows"]} == {"notes-one.md", "notes-two.md"}
    # the original submitted filename (not an internal temp-file name) drives the renamed copy's title
    renamed_names = [row["renamed_file_name"] for row in body["rows"] if row["status"] == "accepted"]
    assert any("notes-one" in name for name in renamed_names)
    assert any("notes-two" in name for name in renamed_names)
    assert not any(name.startswith(("000-", "001-")) for name in renamed_names)
    renamed_paths = [Path(name) for name in renamed_names]
    uploads_dir = workspace / "document_vault" / "uploads" / "renamed"
    assert {p.name for p in uploads_dir.iterdir()} == {p.name for p in renamed_paths}
    originals_dir = workspace / "document_vault" / "uploads" / "originals"
    assert {p.name for p in originals_dir.iterdir()} == {"notes-one.md", "notes-two.md"}
    report_path = workspace / "outputs" / "validation" / "upload-batch-report.yaml"
    assert report_path.is_file()


def test_artefacts_upload_rejects_disallowed_extension_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("script.exe", b"binary-ish", "application/octet-stream"))],
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["rejected"] == 1
    assert body["accepted"] == 0
    assert body["rows"][0]["reason"] == "unsupported_extension"


def test_artefacts_upload_rejects_whole_batch_over_max_files_via_api(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CORROBORLY_UPLOAD_MAX_FILES", "1")
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[
            ("files", ("a.md", b"content a", "text/markdown")),
            ("files", ("b.md", b"content b", "text/markdown")),
        ],
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "upload_batch_too_large"
    uploads_dir = workspace / "document_vault" / "uploads" / "renamed"
    assert list(uploads_dir.iterdir()) == []  # nothing written for a rejected batch


def test_artefacts_upload_enforces_max_file_size_via_api(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CORROBORLY_UPLOAD_MAX_FILE_SIZE_MB", "0.00001")  # ~10 bytes
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("big.md", b"x" * 5000, "text/markdown"))],
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["rejected"] == 1
    assert body["rows"][0]["reason"] == "file_too_large"


def test_artefacts_cross_reference_returns_deterministic_candidates_via_api(
    client: TestClient, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    upload_response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("berth-planning-notes.md", b"notes", "text/markdown"))],
    )
    upload_id = upload_response.json()["data"]["rows"][0]["upload_id"]

    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    client.post(
        "/api/v1/artefacts",
        params={"workspace": str(workspace)},
        json={"title": "Berth Planning Summary", "artefact_type": "report", "path": str(artefact_path)},
    )

    response = client.get(
        "/api/v1/artefacts/cross-reference", params={"workspace": str(workspace), "upload_id": upload_id}
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["candidate_count"] == 1
    assert body["candidates"][0]["target_kind"] == "artefact"
    assert body["links_written"] is False


def test_artefacts_cross_reference_unknown_upload_id_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get(
        "/api/v1/artefacts/cross-reference", params={"workspace": str(workspace), "upload_id": "upload-999"}
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "unknown_upload_id"


def test_artefacts_cross_reference_ai_requires_ai_opt_in(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/artefacts/cross-reference/ai",
        params={"workspace": str(workspace)},
        json={"upload_id": "upload-001"},
    )
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "ai_not_enabled"


def test_artefacts_cross_reference_ai_adds_validated_candidates_via_api(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    claim_response = client.post(
        "/api/v1/claims", params={"workspace": str(workspace)}, json={"text": "Automation reduces turnaround time."}
    )
    claim_id = claim_response.json()["data"]["id"]

    upload_response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("notes.md", b"notes", "text/markdown"))],
    )
    upload_id = upload_response.json()["data"]["rows"][0]["upload_id"]

    _mock_openai(
        monkeypatch,
        f"### CANDIDATE target_kind=claim target_id={claim_id}\nRATIONALE: Related.\n### END CANDIDATE\n",
    )

    response = client.post(
        "/api/v1/artefacts/cross-reference/ai",
        params={"workspace": str(workspace)},
        json={"upload_id": upload_id, "ai": True},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["ai_used"] is True
    assert data["ai_candidate_count"] == 1
    assert any(c["target_id"] == claim_id for c in data["candidates"])


def test_artefacts_cross_reference_apply_writes_only_approved_candidates_via_api(
    client: TestClient, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    upload_response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("berth-planning-notes.md", b"notes", "text/markdown"))],
    )
    upload_id = upload_response.json()["data"]["rows"][0]["upload_id"]

    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    client.post(
        "/api/v1/artefacts",
        params={"workspace": str(workspace)},
        json={"title": "Berth Planning Summary", "artefact_type": "report", "path": str(artefact_path)},
    )
    client.get("/api/v1/artefacts/cross-reference", params={"workspace": str(workspace), "upload_id": upload_id})

    report_path = workspace / "outputs" / "recommendations" / f"cross-reference-{upload_id}.yaml"
    report_data = read_yaml(report_path)
    for candidate in report_data["candidates"]:
        candidate["review_status"] = "accepted"
    write_yaml(report_path, report_data)

    response = client.post(
        "/api/v1/artefacts/cross-reference/apply", params={"workspace": str(workspace)}, json={"upload_id": upload_id}
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["applied_count"] == 1
    assert body["cross_references"][0]["target_kind"] == "artefact"
    # confirm the artefact record itself was never touched -- link lives only on the upload
    artefact_list = client.get("/api/v1/artefacts", params={"workspace": str(workspace)}).json()["data"]
    assert "cross_references" not in artefact_list[0]


def test_artefacts_cross_reference_apply_requires_candidates_first_via_api(
    client: TestClient, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    upload_response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("notes.md", b"notes", "text/markdown"))],
    )
    upload_id = upload_response.json()["data"]["rows"][0]["upload_id"]

    response = client.post(
        "/api/v1/artefacts/cross-reference/apply", params={"workspace": str(workspace)}, json={"upload_id": upload_id}
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "cross_reference_apply_failed"


def test_artefacts_cross_reference_review_sets_status_without_hand_editing_via_api(
    client: TestClient, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    upload_response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("berth-planning-notes.md", b"notes", "text/markdown"))],
    )
    upload_id = upload_response.json()["data"]["rows"][0]["upload_id"]

    artefact_path = workspace / "artefacts" / "reports" / "summary.md"
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    artefact_path.write_text("# Summary", encoding="utf-8")
    client.post(
        "/api/v1/artefacts",
        params={"workspace": str(workspace)},
        json={"title": "Berth Planning Summary", "artefact_type": "report", "path": str(artefact_path)},
    )
    candidates = client.get(
        "/api/v1/artefacts/cross-reference", params={"workspace": str(workspace), "upload_id": upload_id}
    ).json()["data"]["candidates"]
    candidate = candidates[0]

    review_response = client.post(
        "/api/v1/artefacts/cross-reference/candidate-review",
        params={"workspace": str(workspace), "upload_id": upload_id},
        json={"target_kind": candidate["target_kind"], "target_id": candidate["target_id"], "review_status": "accepted"},
    )

    assert review_response.status_code == 200
    assert review_response.json()["data"]["review_status"] == "accepted"

    apply_response = client.post(
        "/api/v1/artefacts/cross-reference/apply", params={"workspace": str(workspace)}, json={"upload_id": upload_id}
    )
    assert apply_response.json()["data"]["applied_count"] == 1


def test_artefacts_cross_reference_review_rejects_invalid_status_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    upload_response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("berth-planning-notes.md", b"notes", "text/markdown"))],
    )
    upload_id = upload_response.json()["data"]["rows"][0]["upload_id"]
    client.get("/api/v1/artefacts/cross-reference", params={"workspace": str(workspace), "upload_id": upload_id})

    response = client.post(
        "/api/v1/artefacts/cross-reference/candidate-review",
        params={"workspace": str(workspace), "upload_id": upload_id},
        json={"target_kind": "artefact", "target_id": "bogus-id", "review_status": "maybe-later"},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "cross_reference_review_failed"


def test_artefacts_uploads_lists_previously_uploaded_artefacts_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("notes.md", b"# Notes", "text/markdown"))],
    )

    response = client.get("/api/v1/artefacts/uploads", params={"workspace": str(workspace)})

    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body) == 1
    assert body[0]["upload_id"] == "upload-001"
    assert body[0]["original_file_name"] == "notes.md"


def test_artefacts_upload_file_serves_renamed_vault_copy_inline_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    upload_response = client.post(
        "/api/v1/artefacts/upload",
        params={"workspace": str(workspace)},
        files=[("files", ("notes.md", b"# Preview Me", "text/markdown"))],
    )
    upload_id = upload_response.json()["data"]["rows"][0]["upload_id"]

    response = client.get(f"/api/v1/artefacts/uploads/{upload_id}/file", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert response.content == b"# Preview Me"
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert response.headers["content-disposition"].startswith("inline")


def test_artefacts_upload_file_unknown_upload_id_returns_404_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/artefacts/uploads/bogus-id/file", params={"workspace": str(workspace)})

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "upload_file_unavailable"


def test_derived_text_build_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Intro\n\nContainer automation reduces delays. It also helps safety.\n", encoding="utf-8")
    client.post("/api/v1/doc/version", params={"workspace": str(workspace)}, json={"target": str(target)})

    response = client.post("/api/v1/doc/derive-text/docv-001", params={"workspace": str(workspace)})

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["section_count"] == 1
    assert body["paragraph_count"] == 1
    assert len(body["paragraphs"][0]["sentences"]) == 2
    assert target.read_text(encoding="utf-8") == "# Intro\n\nContainer automation reduces delays. It also helps safety.\n"


def test_derived_text_build_unknown_version_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post("/api/v1/doc/derive-text/docv-999", params={"workspace": str(workspace)})

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "derived_text_build_failed"


class FakeOpenAiResponse:
    def __init__(self, data: dict) -> None:
        import json

        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.data


def _mock_openai(monkeypatch, output_text: str = "AI output") -> None:
    import corroborly.engine.ai as ai_module

    def fake_urlopen(request):
        return FakeOpenAiResponse({"id": "resp_test", "output_text": output_text})

    monkeypatch.setattr(ai_module, "urlopen", fake_urlopen)


def test_ai_test_route_checks_readiness_without_live_request_by_default(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    response = client.post("/api/v1/ai/test", params={"workspace": str(workspace)}, json={})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["key_loaded"] is True
    assert data["live_request_performed"] is False
    assert "sk-test" not in str(data)


def test_ai_test_route_returns_503_when_not_configured(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # openai_credentials also falls back to a `.env` in Path.cwd(); chdir away
    # from the repo root so this test isn't sensitive to a real dev `.env`.
    monkeypatch.chdir(tmp_path)

    response = client.post("/api/v1/ai/test", params={"workspace": str(workspace)}, json={})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "openai_not_configured"


def test_ai_review_requires_explicit_ai_opt_in(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    response = client.post("/api/v1/ai/review", params={"workspace": str(workspace)}, json={"ai": False})

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "ai_not_enabled"


def test_ai_review_returns_insufficient_evidence_without_network_call(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def fail_if_called(request):
        raise AssertionError("must not call OpenAI when there is no evidence to ground a response in")

    import corroborly.engine.ai as ai_module

    monkeypatch.setattr(ai_module, "urlopen", fail_if_called)

    response = client.post("/api/v1/ai/review", params={"workspace": str(workspace)}, json={"ai": True})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["insufficient_evidence"] is True
    assert data["ai_used"] is False


def test_ai_review_returns_grounded_result_with_mocked_openai(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("bounded evidence text", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    client.post(f"/api/v1/sources/{source_id}/status", params={"workspace": str(workspace)}, json={"new_status": "accepted"})
    client.post("/api/v1/conversion/run", params={"workspace": str(workspace)}, json={})
    _mock_openai(monkeypatch, "Review result")

    response = client.post("/api/v1/ai/review", params={"workspace": str(workspace)}, json={"ai": True})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ai_used"] is True
    assert data["review"] == "Review result"
    assert data["requires_user_review"] is True

    usage_response = client.get("/api/v1/ai/usage-log", params={"workspace": str(workspace)})
    assert usage_response.status_code == 200
    entries = usage_response.json()["data"]
    assert len(entries) == 1
    assert entries[0]["kind"] == "ai_assisted_review"
    assert entries[0]["ai_used"] is True


def test_ai_review_returns_clean_error_when_openai_call_fails(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    """Regression test: `_require_ai` only guards credential loading, not the
    actual `ai_assisted_review` call -- a genuine network/provider failure at
    call time used to propagate as an unhandled 500 instead of the
    documented error envelope. Caught via a real live smoke test hitting a
    real OpenAI request failure (a local TLS error), not assumed."""
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("bounded evidence text", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    client.post(f"/api/v1/sources/{source_id}/status", params={"workspace": str(workspace)}, json={"new_status": "accepted"})
    client.post("/api/v1/conversion/run", params={"workspace": str(workspace)}, json={})

    import corroborly.engine.ai as ai_module
    from urllib.error import URLError

    def failing_urlopen(request):
        raise URLError("simulated provider failure")

    monkeypatch.setattr(ai_module, "urlopen", failing_urlopen)

    response = client.post("/api/v1/ai/review", params={"workspace": str(workspace)}, json={"ai": True})

    assert response.status_code == 502
    assert response.json()["errors"][0]["code"] == "ai_call_failed"


def test_search_ai_query_plan_returns_clean_error_when_openai_call_fails(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("bounded evidence text", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    client.post(f"/api/v1/sources/{source_id}/status", params={"workspace": str(workspace)}, json={"new_status": "accepted"})
    client.post("/api/v1/conversion/run", params={"workspace": str(workspace)}, json={})

    import corroborly.engine.ai as ai_module
    from urllib.error import URLError

    def failing_urlopen(request):
        raise URLError("simulated provider failure")

    monkeypatch.setattr(ai_module, "urlopen", failing_urlopen)

    response = client.post(
        "/api/v1/search/ai-query-plan",
        params={"workspace": str(workspace)},
        json={"ai": True, "external_search": True},
    )

    assert response.status_code == 502
    assert response.json()["errors"][0]["code"] == "ai_call_failed"


def test_ai_usage_log_route_empty_for_fresh_workspace(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/ai/usage-log", params={"workspace": str(workspace)})

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_ai_review_document_requires_both_ai_flags(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Draft text.", encoding="utf-8")

    no_ai = client.post(
        "/api/v1/ai/review-document", params={"workspace": str(workspace)}, json={"target": str(target)}
    )
    assert no_ai.status_code == 400
    assert no_ai.json()["errors"][0]["code"] == "ai_not_enabled"

    no_full_target = client.post(
        "/api/v1/ai/review-document",
        params={"workspace": str(workspace)},
        json={"target": str(target), "ai": True},
    )
    assert no_full_target.status_code == 400
    assert no_full_target.json()["errors"][0]["code"] == "full_target_document_ai_not_enabled"


def test_ai_review_document_grounded_result_with_note_kind_opt_in(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("bounded evidence text", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    client.post(f"/api/v1/sources/{source_id}/status", params={"workspace": str(workspace)}, json={"new_status": "accepted"})
    client.post("/api/v1/conversion/run", params={"workspace": str(workspace)}, json={})
    client.post("/api/v1/notes", params={"workspace": str(workspace)}, json={"text": "A general note.", "kind": "note"})
    client.post("/api/v1/notes", params={"workspace": str(workspace)}, json={"text": "A sensitive meeting note.", "kind": "meeting"})

    target = workspace / "artefacts" / "papers" / "draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Draft text about the study.", encoding="utf-8")
    _mock_openai(monkeypatch, "Strengths: reasonable draft.")

    response = client.post(
        "/api/v1/ai/review-document",
        params={"workspace": str(workspace)},
        json={"target": str(target), "ai": True, "full_target_document_ai": True, "note_kinds": ["note"]},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["ai_used"] is True
    assert data["original_document_modified"] is False
    assert data["note_count"] == 1
    assert data["included_note_kinds"] == ["note"]


def test_ai_novelty_route_writes_ledger(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "paper.txt").write_text("bounded novelty context", encoding="utf-8")
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    scan_sources(workspace, source_root)
    source_id = read_yaml(workspace / "source-register.yaml")["sources"][0]["source_id"]
    client.post(f"/api/v1/sources/{source_id}/status", params={"workspace": str(workspace)}, json={"new_status": "accepted"})
    client.post("/api/v1/conversion/run", params={"workspace": str(workspace)}, json={})
    _mock_openai(monkeypatch, "Novelty assessment")

    response = client.post("/api/v1/ai/novelty", params={"workspace": str(workspace)}, json={"ai": True})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["novelty_not_proven"] is True
    assert data["assessment"] == "Novelty assessment"
    ledger = read_yaml(workspace / "novelty-ledger.yaml")
    assert ledger["assessments"][0]["kind"] == "ai_assisted_novelty_assessment"


def test_ai_rqs_assess_route_rejects_unknown_rq_id(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    response = client.post(
        "/api/v1/ai/rqs/assess", params={"workspace": str(workspace)}, json={"ai": True, "rq_id": "rq-999"}
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "ai_rq_assessment_failed"


@pytest.mark.parametrize(
    "route,kind",
    [
        ("/api/v1/ai/corpus-summary", "corpus_summary"),
        ("/api/v1/ai/claim-check", "claim_checking"),
        ("/api/v1/ai/citation-gaps", "citation_gaps"),
        ("/api/v1/ai/artefact-cross-reference", "artefact_cross_reference"),
        ("/api/v1/ai/source-relevance", "source_relevance"),
        ("/api/v1/ai/abstract-screening", "abstract_screening"),
    ],
)
def test_ai_workspace_report_routes_require_ai_opt_in(
    client: TestClient, tmp_path: Path, monkeypatch, route: str, kind: str
) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    response = client.post(route, params={"workspace": str(workspace)}, json={"ai": False})

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "ai_not_enabled"


def test_ai_query_plan_requires_ai_and_external_search_opt_in(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    ai_only = client.post("/api/v1/search/ai-query-plan", params={"workspace": str(workspace)}, json={"ai": True})
    assert ai_only.status_code == 400
    assert ai_only.json()["errors"][0]["code"] == "external_search_not_enabled"

    neither = client.post("/api/v1/search/ai-query-plan", params={"workspace": str(workspace)}, json={})
    assert neither.status_code == 400
    assert neither.json()["errors"][0]["code"] == "ai_not_enabled"


def test_ai_candidate_review_route_reports_full_text_mode(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def fail_if_called(request):
        raise AssertionError("must not call OpenAI when there is no evidence to ground a response in")

    import corroborly.engine.ai as ai_module

    monkeypatch.setattr(ai_module, "urlopen", fail_if_called)

    response = client.post(
        "/api/v1/search/ai-candidate-review",
        params={"workspace": str(workspace)},
        json={"ai": True, "external_search": True},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["full_text_mode"] == "metadata_and_abstracts_only"
    assert data["full_source_document_ai_opt_in"] is False


def _postgres_test_reachable() -> bool:
    try:
        from corroborly.engine.db_backends import postgres
        from corroborly.engine.db_backends.base import SecondaryBackendCredentials
    except Exception:
        return False
    creds = SecondaryBackendCredentials(host="localhost", port=5432, user=os.environ.get("USER", "postgres"), password="", database="corroborly_test")
    try:
        return postgres.is_reachable(creds)
    except Exception:
        return False


requires_postgres_api = pytest.mark.skipif(
    not _postgres_test_reachable(), reason="No reachable local PostgreSQL test server"
)


@requires_postgres_api
def test_db_backend_status_and_activate_route_via_api(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("CORROBORLY_DB_BACKEND", "postgres")
    monkeypatch.setenv("CORROBORLY_POSTGRES_HOST", "localhost")
    monkeypatch.setenv("CORROBORLY_POSTGRES_PORT", "5432")
    monkeypatch.setenv("CORROBORLY_POSTGRES_USER", os.environ.get("USER", "postgres"))
    monkeypatch.setenv("CORROBORLY_POSTGRES_PASSWORD", "")
    monkeypatch.setenv("CORROBORLY_POSTGRES_DATABASE", "corroborly_test")

    status_response = client.get("/api/v1/db/backend-status", params={"workspace": str(workspace)})
    assert status_response.status_code == 200
    assert status_response.json()["data"]["report"]["configured"] == "postgres"

    activate_response = client.post("/api/v1/db/activate-backend", params={"workspace": str(workspace)})
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["report"]["status"] == "activated"

    sync_response = client.post("/api/v1/db/sync", params={"workspace": str(workspace)}, json={})
    assert sync_response.status_code == 200
    assert sync_response.json()["data"]["report"]["secondary_backend"]["status"] == "mirrored"

    deactivate_response = client.post("/api/v1/db/deactivate-backend", params={"workspace": str(workspace)})
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["data"]["report"]["status"] == "deactivated"


def test_db_activate_backend_route_requires_configuration(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.delenv("CORROBORLY_DB_BACKEND", raising=False)

    response = client.post("/api/v1/db/activate-backend", params={"workspace": str(workspace)})

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "secondary_backend_activation_failed"


# --- transcription (Phase 30, subprocess integration with a sibling SourceScribe checkout) ---


def test_transcription_readiness_route_reports_unconfigured_by_default(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CORROBORLY_SOURCESCRIBE_PATH", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get("/api/v1/transcription/readiness", params={"workspace": str(workspace)})

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["available"] is False
    assert "reason" in body


def test_transcription_upload_limits_route(client: TestClient) -> None:
    response = client.get("/api/v1/transcription/upload/limits")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["max_file_size_mb"] > 0
    assert ".wav" in body["allowed_extensions"]


def test_transcription_upload_registers_job_and_lists_it(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    upload_response = client.post(
        "/api/v1/transcription/upload",
        params={"workspace": str(workspace)},
        files={"file": ("clip.wav", b"\x00\x00" * 800, "audio/wav")},
    )

    assert upload_response.status_code == 200
    job = upload_response.json()["data"]
    assert job["job_id"] == "transcribe-001"
    assert job["status"] == "pending"

    list_response = client.get("/api/v1/transcription/jobs", params={"workspace": str(workspace)})
    assert list_response.status_code == 200
    assert [j["job_id"] for j in list_response.json()["data"]] == ["transcribe-001"]

    get_response = client.get(
        "/api/v1/transcription/jobs/transcribe-001", params={"workspace": str(workspace)}
    )
    assert get_response.status_code == 200
    assert get_response.json()["data"]["job_id"] == "transcribe-001"


def test_transcription_upload_rejects_unsupported_extension(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/transcription/upload",
        params={"workspace": str(workspace)},
        files={"file": ("notes.pdf", b"not audio", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "invalid_transcription_upload"


def test_transcription_job_get_unknown_id_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.get(
        "/api/v1/transcription/jobs/transcribe-999", params={"workspace": str(workspace)}
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "unknown_transcription_job"


def test_transcription_start_returns_503_when_sourcescribe_not_configured(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CORROBORLY_SOURCESCRIBE_PATH", raising=False)
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    client.post(
        "/api/v1/transcription/upload",
        params={"workspace": str(workspace)},
        files={"file": ("clip.wav", b"\x00\x00" * 800, "audio/wav")},
    )

    response = client.post(
        "/api/v1/transcription/jobs/transcribe-001/start",
        params={"workspace": str(workspace)},
        json={},
    )

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "sourcescribe_unavailable"


def test_transcription_start_unknown_job_returns_404(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post(
        "/api/v1/transcription/jobs/transcribe-999/start",
        params={"workspace": str(workspace)},
        json={},
    )

    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "invalid_transcription_job"


def _real_sourcescribe_available() -> bool:
    path = Path("/Users/pedro/Documents/_Projects/transcriber")
    return (path / "main.py").is_file() and (path / ".venv" / "bin" / "python").is_file()


requires_real_sourcescribe_api = pytest.mark.skipif(
    not _real_sourcescribe_available(),
    reason="No real local SourceScribe (transcriber) checkout available for a genuine end-to-end run",
)


def _real_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(8000)
        f.writeframes(b"\x00\x00" * 800)
    return buffer.getvalue()


@requires_real_sourcescribe_api
def test_transcription_start_runs_real_sourcescribe_end_to_end_via_api(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CORROBORLY_SOURCESCRIBE_PATH", "/Users/pedro/Documents/_Projects/transcriber")
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    upload_response = client.post(
        "/api/v1/transcription/upload",
        params={"workspace": str(workspace)},
        files={"file": ("clip.wav", _real_wav_bytes(), "audio/wav")},
    )
    job_id = upload_response.json()["data"]["job_id"]

    start_response = client.post(
        f"/api/v1/transcription/jobs/{job_id}/start",
        params={"workspace": str(workspace)},
        json={"language": "en"},
    )

    assert start_response.status_code == 200
    job = start_response.json()["data"]
    assert job["status"] in {"completed", "failed"}
    if job["status"] == "completed":
        notes_response = client.get("/api/v1/notes", params={"workspace": str(workspace)})
        assert any(n["id"] == job["note_id"] for n in notes_response.json()["data"])
