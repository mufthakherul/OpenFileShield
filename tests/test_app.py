from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import UploadRecord


@pytest.fixture(autouse=True)
def configure_test_runtime(tmp_path: Path):
    from app.config import settings
    from app.main import ensure_sqlite_columns, scanner
    from app.models import Base
    from app.database import engine

    original = {
        "upload_dir": settings.upload_dir,
        "quarantine_dir": settings.quarantine_dir,
        "scan_required": settings.scan_required,
        "async_scan_enabled": settings.async_scan_enabled,
        "app_role": settings.app_role,
        "admin_local_only": settings.admin_local_only,
        "admin_token": settings.admin_token,
    }

    settings.upload_dir = str(tmp_path / "uploads")
    settings.quarantine_dir = str(tmp_path / "quarantine")
    settings.scan_required = False
    settings.async_scan_enabled = False
    settings.app_role = "all"
    settings.admin_local_only = False
    settings.admin_token = "test-admin-token"

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.quarantine_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()

    scanner_ping = scanner.ping
    scanner_scan_file = scanner.scan_file
    scanner.ping = lambda: True
    scanner.scan_file = lambda _: (True, "clean")

    db = SessionLocal()
    db.query(UploadRecord).delete()
    db.commit()
    db.close()

    yield

    settings.upload_dir = original["upload_dir"]
    settings.quarantine_dir = original["quarantine_dir"]
    settings.scan_required = original["scan_required"]
    settings.async_scan_enabled = original["async_scan_enabled"]
    settings.app_role = original["app_role"]
    settings.admin_local_only = original["admin_local_only"]
    settings.admin_token = original["admin_token"]

    scanner.ping = scanner_ping
    scanner.scan_file = scanner_scan_file


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_favicon_returns_no_content(client: TestClient):
    response = client.get("/favicon.ico")
    assert response.status_code == 204


def test_upload_and_admin_stats_flow(client: TestClient):
    files = {"files": ("sample.txt", io.BytesIO(b"hello"), "text/plain")}
    data = {
        "consent": "true",
        "uploader_name": "Tester",
        "uploader_email": "tester@example.com",
        "uploader_notes": "Batch note",
    }
    upload_response = client.post("/api/upload", files=files, data=data)

    assert upload_response.status_code == 200
    body = upload_response.json()
    assert body["total_files"] == 1
    assert body["items"][0]["upload_status"] == "stored"
    assert body["items"][0]["scan_result"] == "clean"

    stats_response = client.get("/api/stats", headers={"x-admin-token": "test-admin-token"})
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["total"] == 1
    assert stats["stored"] == 1


def test_upload_multiple_files_in_one_request(client: TestClient):
    files = [
        ("files", ("alpha.txt", io.BytesIO(b"alpha"), "text/plain")),
        ("files", ("beta.txt", io.BytesIO(b"beta"), "text/plain")),
    ]
    response = client.post("/api/upload", files=files, data={"consent": "true"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_files"] == 2
    assert body["stored"] == 2
    assert [item["original_filename"] for item in body["items"]] == ["alpha.txt", "beta.txt"]


def test_public_role_hides_admin_endpoints(client: TestClient):
    from app.config import settings

    settings.app_role = "public"

    admin_page = client.get("/admin")
    admin_api = client.get("/api/stats", headers={"x-admin-token": "test-admin-token"})

    assert admin_page.status_code == 404
    assert admin_api.status_code == 404


def test_admin_role_enforces_local_only(client: TestClient):
    from app.config import settings

    settings.app_role = "admin"
    settings.admin_local_only = True

    blocked = client.get(
        "/api/stats",
        headers={
            "x-admin-token": "test-admin-token",
            "x-forwarded-for": "8.8.8.8",
        },
    )
    allowed = client.get(
        "/api/stats",
        headers={
            "x-admin-token": "test-admin-token",
            "x-forwarded-for": "127.0.0.1",
        },
    )

    assert blocked.status_code == 403
    assert allowed.status_code == 200


def test_admin_role_root_serves_admin_dashboard(client: TestClient):
    from app.config import settings

    settings.app_role = "admin"
    settings.admin_local_only = False

    response = client.get("/")
    assert response.status_code == 200
    assert "OpenFileShield Admin" in response.text
