import os
import time
import uuid

import httpx
import psycopg2

BASE = "http://127.0.0.1:8000"
SOURCE_IMAGE = "/shared/uploads/generated-smoke.jpg"


def main():
    if not os.path.exists(SOURCE_IMAGE):
        raise RuntimeError(f"Missing generated image: {SOURCE_IMAGE}")

    email = f"queue-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"

    with httpx.Client(timeout=30.0) as client:
        reg = client.post(
            f"{BASE}/auth/register",
            json={"email": email, "password": password, "full_name": "Queue Tester"},
        )
        reg.raise_for_status()
        token = reg.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        project = client.post(
            f"{BASE}/projects",
            headers=headers,
            json={"name": "Queue Smoke", "description": "internal smoke"},
        )
        project.raise_for_status()
        project_id = project.json()["id"]

        with open(SOURCE_IMAGE, "rb") as f:
            files = {"file": ("generated-smoke.jpg", f.read(), "image/jpeg")}

        upload = client.post(f"{BASE}/projects/{project_id}/upload", headers=headers, files=files)
        upload.raise_for_status()
        upload_data = upload.json()
        job_id = upload_data["job_id"]

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        final = None
        for _ in range(40):
            with conn.cursor() as cur:
                cur.execute("SELECT status, error_message FROM jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
                if row and row[0] in ("done", "failed"):
                    final = row
                    break
            time.sleep(3)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM detections WHERE job_id = %s", (job_id,))
            det_count = cur.fetchone()[0]
            cur.execute("SELECT tree_count, avg_confidence, duration_ms FROM job_metrics WHERE job_id = %s", (job_id,))
            metrics = cur.fetchone()

        print(f"PROJECT_ID={project_id}")
        print(f"JOB_ID={job_id}")
        print(f"UPLOAD_STATUS={upload_data['status']}")
        print(f"FINAL_STATUS={(final[0] if final else 'timeout')}")
        print(f"FINAL_ERROR={(final[1] if final else '')}")
        print(f"DETECTIONS={det_count}")
        print(f"METRICS={metrics}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
