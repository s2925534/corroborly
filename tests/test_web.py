from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from researchboss.api.app import create_app
from researchboss.api.auth import clear_all_sessions


TEST_PASSWORD = "test-password"


@pytest.fixture(autouse=True)
def _reset_sessions():
    clear_all_sessions()
    yield
    clear_all_sessions()


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("RESEARCHBOSS_API_PASSWORD", TEST_PASSWORD)
    return TestClient(create_app(), follow_redirects=False)


def test_index_without_session_redirects_to_login(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/login?next=")


def test_login_page_serves_form_without_auth(client: TestClient) -> None:
    response = client.get("/login")

    assert response.status_code == 200
    assert "login-form" in response.text
    assert "password" in response.text


def test_index_with_valid_session_serves_app_shell(client: TestClient) -> None:
    login = client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert login.status_code == 200

    response = client.get("/")

    assert response.status_code == 200
    assert "<title>ResearchBoss</title>" in response.text
    assert "app-main" in response.text


def test_index_redirect_preserves_workspace_query_param(client: TestClient) -> None:
    response = client.get("/?workspace=/some/path")

    assert response.status_code == 303
    location = response.headers["location"]
    assert "workspace" in location


def test_static_assets_are_served(client: TestClient) -> None:
    js_response = client.get("/static/app.js")
    css_response = client.get("/static/styles.css")

    assert js_response.status_code == 200
    assert "text/javascript" in js_response.headers["content-type"] or "application/javascript" in js_response.headers["content-type"]
    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]


def test_logout_invalidates_session_for_index_route(client: TestClient) -> None:
    login = client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert login.status_code == 200
    assert client.get("/").status_code == 200

    client.post("/api/v1/auth/logout")

    assert client.get("/").status_code == 303


def test_index_without_auth_configured_redirects_to_login(monkeypatch) -> None:
    monkeypatch.delenv("RESEARCHBOSS_API_PASSWORD", raising=False)
    unconfigured_client = TestClient(create_app(), follow_redirects=False)

    response = unconfigured_client.get("/")

    assert response.status_code == 303


def test_artefacts_upload_limits_route_via_api(client: TestClient, tmp_path: Path) -> None:
    from researchboss.engine.workspace import init_workspace

    workspace = tmp_path / "workspace"
    init_workspace(workspace, project_name="Test", project_type="M.Phil", topic="Topic")
    login = client.post("/api/v1/auth/login", json={"password": TEST_PASSWORD})
    assert login.status_code == 200

    response = client.get("/api/v1/artefacts/upload/limits", params={"workspace": str(workspace)})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["max_files"] == 25
    assert data["max_file_size_mb"] == 50.0
    assert ".md" in data["allowed_extensions"]
