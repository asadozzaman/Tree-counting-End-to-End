import os
import time
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras
import redis
from ultralytics import YOLO


def database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://tree_user:tree_pass@postgres:5432/tree_saas")


def redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://redis:6379/0")


def queue_key() -> str:
    return os.getenv("JOB_QUEUE_KEY", "jobs:queue")


def model_path() -> str:
    return os.getenv("MODEL_PATH", "/models/tree_yolo26s_best.pt")


def infer_conf() -> float:
    return float(os.getenv("INFER_CONF", "0.25"))


def infer_iou() -> float:
    return float(os.getenv("INFER_IOU", "0.45"))


def get_job_input_asset(cur, job_id: str):
    cur.execute(
        """
        SELECT a.id, a.file_path, a.mime_type
        FROM assets a
        WHERE a.job_id = %s AND a.kind = 'input'
        ORDER BY a.created_at ASC
        LIMIT 1
        """,
        (job_id,),
    )
    return cur.fetchone()


def set_job_running(cur, job_id: str) -> None:
    cur.execute(
        """
        UPDATE jobs
        SET status='running', started_at=NOW(), updated_at=NOW(), error_message=NULL
        WHERE id=%s
        """,
        (job_id,),
    )


def set_job_failed(cur, job_id: str, message: str) -> None:
    cur.execute(
        """
        UPDATE jobs
        SET status='failed', error_message=%s, completed_at=NOW(), updated_at=NOW()
        WHERE id=%s
        """,
        (message[:2000], job_id),
    )


def set_job_done(cur, job_id: str) -> None:
    cur.execute(
        """
        UPDATE jobs
        SET status='done', completed_at=NOW(), updated_at=NOW(), error_message=NULL
        WHERE id=%s
        """,
        (job_id,),
    )


def save_detections_and_metrics(cur, job_id: str, project_id: str, asset_id: str, detections: list, duration_ms: int) -> None:
    cur.execute("DELETE FROM detections WHERE job_id=%s", (job_id,))

    for d in detections:
        cur.execute(
            """
            INSERT INTO detections(job_id, asset_id, class_id, class_name, x1, y1, x2, y2, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                job_id,
                asset_id,
                d["class_id"],
                d["class_name"],
                d["x1"],
                d["y1"],
                d["x2"],
                d["y2"],
                d["confidence"],
            ),
        )

    tree_count = len(detections)
    avg_conf = round(sum(d["confidence"] for d in detections) / tree_count, 6) if tree_count else 0.0

    cur.execute(
        """
        INSERT INTO job_metrics(job_id, project_id, tree_count, avg_confidence, duration_ms)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (job_id)
        DO UPDATE SET
            tree_count = EXCLUDED.tree_count,
            avg_confidence = EXCLUDED.avg_confidence,
            duration_ms = EXCLUDED.duration_ms
        """,
        (job_id, project_id, tree_count, avg_conf, duration_ms),
    )


def run_inference(model: YOLO, file_path: str) -> list:
    result = model.predict(source=file_path, conf=infer_conf(), iou=infer_iou(), verbose=False)[0]
    names = result.names
    detections = []
    if result.boxes is None:
        return detections

    boxes = result.boxes
    xyxy = boxes.xyxy.cpu().tolist()
    confs = boxes.conf.cpu().tolist()
    classes = boxes.cls.cpu().tolist()

    for idx in range(len(xyxy)):
        c = int(classes[idx])
        detections.append(
            {
                "class_id": c,
                "class_name": str(names.get(c, str(c))),
                "x1": float(xyxy[idx][0]),
                "y1": float(xyxy[idx][1]),
                "x2": float(xyxy[idx][2]),
                "y2": float(xyxy[idx][3]),
                "confidence": float(confs[idx]),
            }
        )

    return detections


def process_job(conn, model: YOLO, job_id: str) -> None:
    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, project_id, status FROM jobs WHERE id=%s", (job_id,))
            job = cur.fetchone()
            if not job:
                print(f"job not found: {job_id}", flush=True)
                return

            set_job_running(cur, job_id)

    started = time.time()

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            asset = get_job_input_asset(cur, job_id)
            if not asset:
                raise RuntimeError("No input asset found for job")

        file_path = asset["file_path"]
        if not Path(file_path).exists():
            raise RuntimeError(f"Input file missing: {file_path}")

        detections = run_inference(model, file_path)
        duration_ms = int((time.time() - started) * 1000)

        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                save_detections_and_metrics(
                    cur=cur,
                    job_id=job_id,
                    project_id=str(job["project_id"]),
                    asset_id=str(asset["id"]),
                    detections=detections,
                    duration_ms=duration_ms,
                )
                set_job_done(cur, job_id)

        print(f"processed job={job_id} detections={len(detections)} duration_ms={duration_ms}", flush=True)

    except Exception as exc:
        with conn:
            with conn.cursor() as cur:
                set_job_failed(cur, job_id, str(exc))
        print(f"failed job={job_id}: {exc}", flush=True)


def main() -> None:
    print(f"worker boot at {datetime.utcnow().isoformat()}Z", flush=True)
    print(f"loading model from {model_path()}", flush=True)
    model = YOLO(model_path())
    print("model loaded", flush=True)

    r = redis.Redis.from_url(redis_url(), decode_responses=True)
    conn = psycopg2.connect(database_url())

    print(f"listening queue={queue_key()} redis={redis_url()}", flush=True)

    try:
        while True:
            item = r.blpop(queue_key(), timeout=5)
            if not item:
                continue
            _, job_id = item
            process_job(conn, model, job_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
