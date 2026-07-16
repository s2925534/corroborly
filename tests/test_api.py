from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ledgerly.api.app import create_app
from ledgerly.api.auth import clear_all_sessions
from ledgerly.core.yamlio import read_yaml, write_yaml
from ledgerly.engine.sources import scan_sources
from ledgerly.engine.workspace import init_workspace


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
    monkeypatch.setenv("LEDGERLY_API_USERNAME", TEST_USERNAME)
    monkeypatch.setenv("LEDGERLY_API_PASSWORD", TEST_PASSWORD)
    test_client = TestClient(create_app())
    login_response = test_client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert login_response.status_code == 200, login_response.text
    return test_client


@pytest.fixture()
def unauthenticated_client(monkeypatch) -> TestClient:
    """Username/password configured, but no session established — for testing the auth gate itself."""
    monkeypatch.setenv("LEDGERLY_API_USERNAME", TEST_USERNAME)
    monkeypatch.setenv("LEDGERLY_API_PASSWORD", TEST_PASSWORD)
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


def test_export_corpus_via_api(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")

    response = client.post("/api/v1/export/corpus", params={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert Path(data["manifest_path"]).is_file()
    assert data["included_count"] == 0
    assert data["skipped_count"] == 0


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
    monkeypatch.delenv("LEDGERLY_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_fails_closed_when_auth_not_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LEDGERLY_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.get("/api/v1/projects/status", params={"workspace": str(tmp_path)})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "auth_not_configured"


def test_login_fails_closed_when_auth_not_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LEDGERLY_API_USERNAME", raising=False)
    monkeypatch.delenv("LEDGERLY_API_PASSWORD", raising=False)
    bare_client = TestClient(create_app())

    response = bare_client.post("/api/v1/auth/login", json={"username": "anyone", "password": "anything"})

    assert response.status_code == 503
    assert response.json()["errors"][0]["code"] == "auth_not_configured"


def test_login_fails_closed_when_only_password_configured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LEDGERLY_API_USERNAME", raising=False)
    monkeypatch.setenv("LEDGERLY_API_PASSWORD", TEST_PASSWORD)
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
    assert rebuild_response.json()["data"]["report"]["status"] == "rebuilt"


def test_resolve_workspace_accepts_relative_path_inside_configured_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "nas-volume"
    root.mkdir()
    workspace = root / "project-a"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("LEDGERLY_WORKSPACE_ROOT", str(root))

    response = client.get("/api/v1/projects/status", params={"workspace": "project-a"})

    assert response.status_code == 200


def test_resolve_workspace_accepts_absolute_path_inside_configured_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "nas-volume"
    root.mkdir()
    workspace = root / "project-a"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("LEDGERLY_WORKSPACE_ROOT", str(root))

    response = client.get("/api/v1/projects/status", params={"workspace": str(workspace)})

    assert response.status_code == 200


def test_resolve_workspace_rejects_path_outside_configured_root(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "nas-volume"
    root.mkdir()
    outside_workspace = tmp_path / "outside" / "workspace"
    init_workspace(outside_workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    monkeypatch.setenv("LEDGERLY_WORKSPACE_ROOT", str(root))

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
    monkeypatch.setenv("LEDGERLY_WORKSPACE_ROOT", str(root))

    response = client.get(
        "/api/v1/projects/status", params={"workspace": "../outside/workspace"}
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "workspace_outside_root"


def test_resolve_workspace_without_configured_root_keeps_local_first_flexibility(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("LEDGERLY_WORKSPACE_ROOT", raising=False)
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
    monkeypatch.setenv("LEDGERLY_UPLOAD_MAX_FILES", "1")
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
    monkeypatch.setenv("LEDGERLY_UPLOAD_MAX_FILE_SIZE_MB", "0.00001")  # ~10 bytes
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
