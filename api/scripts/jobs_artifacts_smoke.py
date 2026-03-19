import csv
import io
import json
import os
import time
import uuid
from pathlib import Path

import httpx

BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
SAMPLE = Path("/shared/uploads/sample-a.jpg")


def wait_done(client: httpx.Client, headers: dict, job_id: str, timeout_sec: int = 180):
    started = time.time()
    while time.time() - started < timeout_sec:
        res = client.get(f"{BASE}/jobs/{job_id}", headers=headers)
        res.raise_for_status()
        body = res.json()
        if body["status"] in {"done", "failed"}:
            return body
        time.sleep(2)
    raise RuntimeError("job timeout waiting for done/failed")


def assert_json_schema(payload: dict):
    assert set(payload.keys()) == {"job", "metrics", "detections"}
    assert set(payload["job"].keys()) >= {"id", "project_id", "status", "conf_threshold", "iou_threshold"}
    assert set(payload["metrics"].keys()) == {"tree_count", "avg_confidence", "duration_ms"}
    assert isinstance(payload["detections"], list)
    if payload["detections"]:
        assert set(payload["detections"][0].keys()) == {"id", "class_id", "class_name", "bbox", "conf"}


def assert_csv_schema(raw: bytes):
    text = raw.decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows, "CSV returned no rows"
    assert set(rows[0].keys()) == {"id", "class_id", "class_name", "x1", "y1", "x2", "y2", "confidence"}


def main():
    if not SAMPLE.exists():
        raise RuntimeError(f"missing sample image: {SAMPLE}")

    email = f"job-art-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    with httpx.Client(timeout=60.0) as client:
        reg = client.post(
            f"{BASE}/auth/register",
            json={"email": email, "password": password, "full_name": "Artifact Smoke"},
        )
        reg.raise_for_status()
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        proj = client.post(
            f"{BASE}/projects",
            headers=headers,
            json={"name": "Artifacts Smoke", "description": "jobs endpoints smoke"},
        )
        proj.raise_for_status()
        project_id = proj.json()["id"]

        files = {"file": ("sample-a.jpg", SAMPLE.read_bytes(), "image/jpeg")}
        up = client.post(f"{BASE}/projects/{project_id}/upload", headers=headers, files=files)
        up.raise_for_status()
        job_id = up.json()["job_id"]

        detail = wait_done(client, headers, job_id)
        if detail["status"] != "done":
            raise RuntimeError(f"job did not complete successfully: {detail['status']} err={detail.get('error_message')}")

        csv_res = client.get(f"{BASE}/jobs/{job_id}/download/csv", headers=headers)
        csv_res.raise_for_status()
        csv_path = csv_res.headers.get("x-artifact-path")
        if not csv_path or not Path(csv_path).exists():
            raise RuntimeError(f"csv artifact missing: {csv_path}")
        assert_csv_schema(csv_res.content)

        json_res = client.get(f"{BASE}/jobs/{job_id}/download/json", headers=headers)
        json_res.raise_for_status()
        json_path = json_res.headers.get("x-artifact-path")
        if not json_path or not Path(json_path).exists():
            raise RuntimeError(f"json artifact missing: {json_path}")
        json_payload = json.loads(json_res.content.decode("utf-8"))
        assert_json_schema(json_payload)

        img_res = client.get(f"{BASE}/jobs/{job_id}/annotated-image", headers=headers)
        img_res.raise_for_status()
        img_path = img_res.headers.get("x-artifact-path")
        if not img_path or not Path(img_path).exists():
            raise RuntimeError(f"annotated artifact missing: {img_path}")

    print(f"JOB_ID={job_id}")
    print(f"TREE_COUNT={detail['metrics']['tree_count'] if detail.get('metrics') else 0}")
    print(f"CSV_PATH={csv_path}")
    print(f"JSON_PATH={json_path}")
    print(f"ANNOTATED_PATH={img_path}")
    print("SCHEMA_VALIDATION=PASS")


if __name__ == "__main__":
    main()