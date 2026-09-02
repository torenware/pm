from pathlib import Path

from fastapi.testclient import TestClient

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