from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from researchboss.api.app import create_app
from researchboss.api.auth import clear_all_sessions
from researchboss.core.yamlio import read_yaml
from researchboss.engine.sources import scan_sources
from researchboss.engine.workspace import init_workspace


TEST_PASSWORD = "test-password"


@pytest.fixture(autouse=True)
def _reset_sessions():
    clear_all_sessions()
    yield
    clear_all_sessions()


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """An already-authenticated client, for tests that exercise route behavior, not auth itself."""
    monkeypatch.setenv("RESEARCHBOSS_API_PASSWORD", TEST_PASSWORD)
    test_client = TestClient(create_app())
    login_response = test_client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert login_response.status_code == 200, login_response.text
    return test_client


@pytest.fixture()
def unauthenticated_client(monkeypatch) -> TestClient:
    """Password configured, but no session established — for testing the auth gate itself."""
    monkeypatch.setenv("RESEARCHBOSS_API_PASSWORD", TEST_PASSWORD)
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
    monkeypatch.delenv("RESEARCHBOSS_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_fails_closed_when_auth_not_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RESEARCHBOSS_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.get("/api/v1/projects/status", params={"workspace": str(tmp_path)})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "auth_not_configured"


def test_login_fails_closed_when_auth_not_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RESEARCHBOSS_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.post("/api/v1/auth/login", json={"password": "anything"})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "auth_not_configured"


def test_login_rejects_wrong_password(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post("/api/v1/auth/login", json={"password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "invalid_credentials"


def test_protected_route_rejects_request_without_session(unauthenticated_client: TestClient, tmp_path: Path) -> None:
    response = unauthenticated_client.get("/api/v1/projects/status", params={"workspace": str(tmp_path)})

    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "unauthorized"


def test_login_success_grants_access_via_cookie(unauthenticated_client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    login_response = unauthenticated_client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert login_response.status_code == 200
    assert "token" in login_response.json()["data"]

    status_response = unauthenticated_client.get("/api/v1/projects/status", params={"workspace": str(workspace)})
    assert status_response.status_code == 200


def test_login_success_grants_access_via_bearer_token(unauthenticated_client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    login_response = unauthenticated_client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
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
    login_response = unauthenticated_client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert login_response.status_code == 200

    logout_response = unauthenticated_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    response = unauthenticated_client.get("/api/v1/projects/status", params={"workspace": str(workspace)})
    assert response.status_code == 401


def test_password_is_never_echoed_back_in_login_response(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})

    assert TEST_PASSWORD not in response.text
