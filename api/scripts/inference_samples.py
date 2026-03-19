import os
import time
import uuid

import httpx
import psycopg2

BASE = "http://127.0.0.1:8000"
SAMPLE_PATHS = [
    "/shared/uploads/sample-a.jpg",
    "/shared/uploads/sample-b.jpg",
]


def wait_for_final(conn, job_id: str, timeout_sec: int = 180):
    started = time.time()
    while time.time() - started < timeout_sec:
        with conn.cursor() as cur:
            cur.execute("SELECT status, error_message FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
            if row and row[0] in ("done", "failed"):
                return row
        time.sleep(3)
    return ("timeout", "timed out")


def main():
    for p in SAMPLE_PATHS:
        if not os.path.exists(p):
            raise RuntimeError(f"Missing sample image: {p}")

    email = f"infer-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    with httpx.Client(timeout=30.0) as client:
        reg = client.post(
            f"{BASE}/auth/register",
            json={"email": email, "password": password, "full_name": "Inference Tester"},
        )
        reg.raise_for_status()
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        project = client.post(
            f"{BASE}/projects",
            headers=headers,
            json={"name": "Inference Samples", "description": "threshold smoke"},
        )
        project.raise_for_status()
        project_id = project.json()["id"]

        jobs = []

        with open(SAMPLE_PATHS[0], "rb") as f:
            files = {"file": ("sample-a.jpg", f.read(), "image/jpeg")}
        up1 = client.post(f"{BASE}/projects/{project_id}/upload", headers=headers, files=files)
        up1.raise_for_status()
        jobs.append(up1.json()["job_id"])

        with open(SAMPLE_PATHS[1], "rb") as f:
            files = {"file": ("sample-b.jpg", f.read(), "image/jpeg")}
        up2 = client.post(
            f"{BASE}/projects/{project_id}/upload",
            headers=headers,
            files=files,
            data={"conf_threshold": "0.40", "iou_threshold": "0.60"},
        )
        up2.raise_for_status()
        jobs.append(up2.json()["job_id"])

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        for job_id in jobs:
            final = wait_for_final(conn, job_id)

            with conn.cursor() as cur:
                cur.execute("SELECT conf_threshold, iou_threshold FROM jobs WHERE id = %s", (job_id,))
                thresholds = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM detections WHERE job_id = %s", (job_id,))
                det_count = cur.fetchone()[0]
                cur.execute(
                    "SELECT tree_count, avg_confidence, duration_ms FROM job_metrics WHERE job_id = %s",
                    (job_id,),
                )
                metrics = cur.fetchone()

            matches = bool(metrics and det_count == metrics[0])
            print(f"JOB_ID={job_id}")
            print(f"FINAL_STATUS={final[0]}")
            print(f"ERROR={final[1]}")
            print(f"THRESHOLDS={thresholds}")
            print(f"DETECTION_COUNT={det_count}")
            print(f"METRICS={metrics}")
            print(f"COUNT_MATCHES_DETECTIONS={matches}")
            print("---")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
