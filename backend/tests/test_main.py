from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.main import app, create_app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_temporary_page_that_calls_health_api() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Project Management MVP" in response.text
    assert 'fetch("/api/health")' in response.text


def test_static_export_serves_index_and_nested_assets(tmp_path: Path) -> None:
    asset_dir = tmp_path / "_next" / "static"
    asset_dir.mkdir(parents=True)
    (tmp_path / "index.html").write_text(
        '<h1>Kanban Studio</h1><script src="/_next/static/app.js"></script>'
    )
    (asset_dir / "app.js").write_text("window.kanbanLoaded = true;")
    export_client = TestClient(create_app(tmp_path))

    index_response = export_client.get("/")
    asset_response = export_client.get("/_next/static/app.js")

    assert index_response.status_code == 200
    assert "Kanban Studio" in index_response.text
    assert asset_response.status_code == 200
    assert asset_response.text == "window.kanbanLoaded = true;"


def test_login_creates_http_only_session_and_allows_protected_access() -> None:
    auth_client = TestClient(create_app(session_secret="test-secret"))

    login_response = auth_client.post(
        "/api/login",
        json={"username": "user", "password": "password"},
    )

    assert login_response.status_code == 200
    assert login_response.json() == {"username": "user"}
    cookie = login_response.headers["set-cookie"]
    assert f"{SESSION_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=28800" in cookie
    assert auth_client.get("/api/session").json() == {"username": "user"}
    assert auth_client.get("/api/protected").status_code == 200


def test_login_rejects_invalid_credentials() -> None:
    auth_client = TestClient(create_app(session_secret="test-secret"))

    response = auth_client.post(
        "/api/login",
        json={"username": "user", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    assert SESSION_COOKIE not in auth_client.cookies


def test_protected_routes_reject_missing_and_invalid_cookies() -> None:
    auth_client = TestClient(create_app(session_secret="test-secret"))

    assert auth_client.get("/api/session").status_code == 401
    auth_client.cookies.set(SESSION_COOKIE, "invalid.cookie")
    assert auth_client.get("/api/protected").status_code == 401


def test_logout_invalidates_session() -> None:
    auth_client = TestClient(create_app(session_secret="test-secret"))
    auth_client.post(
        "/api/login",
        json={"username": "user", "password": "password"},
    )
    session_cookie = auth_client.cookies[SESSION_COOKIE]

    response = auth_client.post("/api/logout")

    assert response.status_code == 204
    auth_client.cookies.set(SESSION_COOKIE, session_cookie)
    assert auth_client.get("/api/session").status_code == 401


def test_expired_session_is_rejected() -> None:
    current_time = [1000.0]
    auth_client = TestClient(
        create_app(
            session_secret="test-secret",
            now=lambda: current_time[0],
            session_max_age=10,
        )
    )
    auth_client.post(
        "/api/login",
        json={"username": "user", "password": "password"},
    )

    current_time[0] += 11

    assert auth_client.get("/api/session").status_code == 401