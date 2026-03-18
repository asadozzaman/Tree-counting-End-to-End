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


def test_auth_and_project_crud_flow():
    _clean_db()

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    register_res = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert register_res.status_code == 201
    register_body = register_res.json()
    assert register_body["token_type"] == "bearer"
    assert register_body["access_token"]

    dup_res = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert dup_res.status_code == 409

    login_res = client.post("/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    bad_login_res = client.post("/auth/login", json={"email": email, "password": "wrongpass123"})
    assert bad_login_res.status_code == 401

    unauthorized_list = client.get("/projects")
    assert unauthorized_list.status_code == 403

    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/projects",
        json={"name": "Farm Block A", "description": "north side"},
        headers=headers,
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    list_res = client.get("/projects", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    get_res = client.get(f"/projects/{project_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Farm Block A"

    del_res = client.delete(f"/projects/{project_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    get_deleted = client.get(f"/projects/{project_id}", headers=headers)
    assert get_deleted.status_code == 404
