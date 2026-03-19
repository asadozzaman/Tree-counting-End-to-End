import os
import uuid

import psycopg2
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _db_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required for tests")
    return value


def _clean_db() -> None:
    with psycopg2.connect(_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE job_metrics, detections, assets, jobs, projects, users RESTART IDENTITY CASCADE")


def _register_and_login() -> str:
    email = f"upload-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    reg = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Uploader"},
    )
    assert reg.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def _create_project(headers: dict) -> str:
    res = client.post(
        "/projects",
        headers=headers,
        json={"name": "Upload Project", "description": "for upload tests"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_upload_valid_creates_job_and_asset_records():
    _clean_db()
    os.environ["MAX_UPLOAD_BYTES"] = "10485760"

    token = _register_and_login()
    headers = {"Authorization": f"Bearer {token}"}
    project_id = _create_project(headers)

    files = {
        "file": ("sample.jpg", b"\xff\xd8\xff\xdbfakejpeg", "image/jpeg")
    }
    upload = client.post(f"/projects/{project_id}/upload", files=files, headers=headers)
    assert upload.status_code == 201
    payload = upload.json()
    assert payload["status"] == "queued"

    with psycopg2.connect(_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM jobs WHERE id = %s", (payload["job_id"],))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "queued"

            cur.execute("SELECT kind, job_id FROM assets WHERE id = %s", (payload["asset_id"],))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "input"
            assert str(row[1]) == payload["job_id"]


def test_upload_invalid_file_type_rejected():
    _clean_db()
    token = _register_and_login()
    headers = {"Authorization": f"Bearer {token}"}
    project_id = _create_project(headers)

    files = {
        "file": ("sample.txt", b"plain text", "text/plain")
    }
    upload = client.post(f"/projects/{project_id}/upload", files=files, headers=headers)
    assert upload.status_code == 415


def test_upload_oversized_file_rejected():
    _clean_db()
    os.environ["MAX_UPLOAD_BYTES"] = "64"

    token = _register_and_login()
    headers = {"Authorization": f"Bearer {token}"}
    project_id = _create_project(headers)

    files = {
        "file": ("sample.png", b"a" * 200, "image/png")
    }
    upload = client.post(f"/projects/{project_id}/upload", files=files, headers=headers)
    assert upload.status_code == 413
