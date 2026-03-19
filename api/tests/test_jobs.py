import csv
import json
import os
import uuid
from pathlib import Path

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


def _auth_headers() -> dict:
    email = f"jobs-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    reg = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Jobs Tester"},
    )
    assert reg.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_project(headers: dict) -> str:
    res = client.post(
        "/projects",
        headers=headers,
        json={"name": "Job Endpoints", "description": "artifact tests"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def _seed_done_job(project_id: str) -> tuple[str, str]:
    upload_root = Path("/shared/uploads")
    artifacts_root = upload_root / "artifacts"
    upload_root.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    input_path = upload_root / f"{uuid.uuid4().hex}_input.jpg"
    annotated_path = artifacts_root / f"{uuid.uuid4().hex}_annotated.jpg"

    input_bytes = b"\xff\xd8\xff\xdbfakejpg\xff\xd9"
    annotated_bytes = b"\xff\xd8\xff\xdbannotated\xff\xd9"
    input_path.write_bytes(input_bytes)
    annotated_path.write_bytes(annotated_bytes)

    with psycopg2.connect(_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs(project_id, status, input_type, conf_threshold, iou_threshold)
                VALUES (%s, 'done', 'image', 0.25, 0.45)
                RETURNING id
                """,
                (project_id,),
            )
            job_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO assets(project_id, job_id, kind, file_path, mime_type, size_bytes)
                VALUES (%s, %s, 'input', %s, 'image/jpeg', %s)
                """,
                (project_id, str(job_id), str(input_path), input_path.stat().st_size),
            )

            cur.execute(
                """
                INSERT INTO assets(project_id, job_id, kind, file_path, mime_type, size_bytes)
                VALUES (%s, %s, 'annotated', %s, 'image/jpeg', %s)
                """,
                (project_id, str(job_id), str(annotated_path), annotated_path.stat().st_size),
            )

            cur.execute(
                """
                INSERT INTO detections(job_id, asset_id, class_id, class_name, x1, y1, x2, y2, confidence)
                VALUES (%s, NULL, 0, 'tree', 10, 12, 40, 60, 0.91),
                       (%s, NULL, 0, 'tree', 100, 120, 180, 220, 0.73)
                """,
                (str(job_id), str(job_id)),
            )

            cur.execute(
                """
                INSERT INTO job_metrics(job_id, project_id, tree_count, avg_confidence, duration_ms)
                VALUES (%s, %s, 2, 0.82, 145)
                """,
                (str(job_id), project_id),
            )

    return str(job_id), str(annotated_path)


def test_job_endpoints_and_artifacts_downloads():
    _clean_db()

    headers = _auth_headers()
    project_id = _create_project(headers)
    job_id, annotated_path = _seed_done_job(project_id)

    detail = client.get(f"/jobs/{job_id}", headers=headers)
    assert detail.status_code == 200
    detail_body = detail.json()

    assert detail_body["id"] == job_id
    assert detail_body["status"] == "done"
    assert detail_body["metrics"]["tree_count"] == 2
    assert isinstance(detail_body["detections"], list)
    assert len(detail_body["detections"]) == 2
    assert detail_body["assets"]["csv_download_url"].endswith("/download/csv")
    assert detail_body["assets"]["json_download_url"].endswith("/download/json")

    csv_res = client.get(f"/jobs/{job_id}/download/csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    csv_path = csv_res.headers.get("x-artifact-path")
    assert csv_path
    assert Path(csv_path).exists()

    csv_text = csv_res.content.decode("utf-8")
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert rows
    header_keys = set(rows[0].keys())
    assert header_keys == {"id", "class_id", "class_name", "x1", "y1", "x2", "y2", "confidence"}
    detection_rows = [r for r in rows if r["class_name"] == "tree"]
    assert len(detection_rows) == 2

    json_res = client.get(f"/jobs/{job_id}/download/json", headers=headers)
    assert json_res.status_code == 200
    assert "application/json" in json_res.headers.get("content-type", "")
    json_path = json_res.headers.get("x-artifact-path")
    assert json_path
    assert Path(json_path).exists()

    payload = json.loads(json_res.content.decode("utf-8"))
    assert set(payload.keys()) == {"job", "metrics", "detections"}
    assert set(payload["job"].keys()) >= {"id", "project_id", "status", "conf_threshold", "iou_threshold"}
    assert set(payload["metrics"].keys()) == {"tree_count", "avg_confidence", "duration_ms"}
    assert isinstance(payload["detections"], list)
    assert len(payload["detections"]) == 2
    assert set(payload["detections"][0].keys()) == {"id", "class_id", "class_name", "bbox", "conf"}

    img_res = client.get(f"/jobs/{job_id}/annotated-image", headers=headers)
    assert img_res.status_code == 200
    assert img_res.headers.get("x-artifact-path") == annotated_path
    assert Path(annotated_path).exists()
    assert len(img_res.content) > 0
