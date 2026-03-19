import os
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional
from uuid import UUID
import uuid

import psycopg2
import psycopg2.extras
import redis
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

app = FastAPI(title="Tree Counting SaaS API", version="0.1.0")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=True)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


class DeleteResponse(BaseModel):
    deleted: bool
    id: UUID


class UploadResponse(BaseModel):
    job_id: UUID
    asset_id: UUID
    project_id: UUID
    status: str
    file_path: str
    mime_type: str
    size_bytes: int
    conf_threshold: float
    iou_threshold: float


class DetectionResponse(BaseModel):
    id: int
    class_id: int
    class_name: str
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    created_at: datetime


class JobMetricsResponse(BaseModel):
    tree_count: int
    avg_confidence: float
    duration_ms: int


class JobAssetsResponse(BaseModel):
    input_image: Optional[str] = None
    annotated_image: Optional[str] = None
    csv_download_url: str
    json_download_url: str


class JobDetailResponse(BaseModel):
    id: UUID
    project_id: UUID
    status: str
    input_type: str
    error_message: Optional[str]
    conf_threshold: float
    iou_threshold: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    metrics: Optional[JobMetricsResponse] = None
    detections: list[DetectionResponse] = Field(default_factory=list)
    assets: JobAssetsResponse


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value


def redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://redis:6379/0")


def job_queue_key() -> str:
    return os.getenv("JOB_QUEUE_KEY", "jobs:queue")


def jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-only-secret-change-me")


def jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def jwt_expiry_minutes() -> int:
    return int(os.getenv("JWT_EXPIRE_MINUTES", "120"))


def max_upload_bytes() -> int:
    return int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))


def uploads_dir() -> Path:
    root = Path(os.getenv("UPLOAD_DIR", "/shared/uploads"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def artifacts_dir() -> Path:
    root = uploads_dir() / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def csv_artifact_path(job_id: UUID) -> Path:
    return artifacts_dir() / f"{job_id}_detections.csv"


def json_artifact_path(job_id: UUID) -> Path:
    return artifacts_dir() / f"{job_id}_detections.json"


def get_owned_job_or_404(cur, job_id: UUID, user_id: UUID):
    cur.execute(
        """
        SELECT j.id, j.project_id, j.status, j.input_type, j.error_message,
               j.conf_threshold, j.iou_threshold, j.started_at, j.completed_at,
               j.created_at, j.updated_at
        FROM jobs j
        JOIN projects p ON p.id = j.project_id
        WHERE j.id = %s AND p.user_id = %s
        """,
        (str(job_id), str(user_id)),
    )
    job = cur.fetchone()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def fetch_job_metrics(cur, job_id: UUID):
    cur.execute(
        """
        SELECT tree_count, avg_confidence, duration_ms
        FROM job_metrics
        WHERE job_id = %s
        """,
        (str(job_id),),
    )
    return cur.fetchone()


def fetch_job_detections(cur, job_id: UUID):
    cur.execute(
        """
        SELECT id, class_id, class_name, x1, y1, x2, y2, confidence, created_at
        FROM detections
        WHERE job_id = %s
        ORDER BY id ASC
        """,
        (str(job_id),),
    )
    return cur.fetchall()


def fetch_job_assets(cur, job_id: UUID):
    cur.execute(
        """
        SELECT kind, file_path
        FROM assets
        WHERE job_id = %s
        """,
        (str(job_id),),
    )
    out = {"input_image": None, "annotated_image": None}
    for row in cur.fetchall():
        if row["kind"] == "input":
            out["input_image"] = row["file_path"]
        if row["kind"] == "annotated":
            out["annotated_image"] = row["file_path"]
    return out


def write_detections_csv(path: Path, detections: list, metrics) -> None:
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["id", "class_id", "class_name", "x1", "y1", "x2", "y2", "confidence"],
        )
        writer.writeheader()
        for d in detections:
            writer.writerow(
                {
                    "id": d["id"],
                    "class_id": d["class_id"],
                    "class_name": d["class_name"],
                    "x1": d["x1"],
                    "y1": d["y1"],
                    "x2": d["x2"],
                    "y2": d["y2"],
                    "confidence": d["confidence"],
                }
            )

        writer.writerow({})
        writer.writerow({"id": "tree_count", "class_id": metrics["tree_count"] if metrics else 0})
        writer.writerow({"id": "avg_confidence", "class_id": metrics["avg_confidence"] if metrics else 0.0})
        writer.writerow({"id": "duration_ms", "class_id": metrics["duration_ms"] if metrics else 0})


def write_detections_json(path: Path, job, detections: list, metrics) -> None:
    payload = {
        "job": {
            "id": str(job["id"]),
            "project_id": str(job["project_id"]),
            "status": job["status"],
            "conf_threshold": float(job["conf_threshold"]) if job["conf_threshold"] is not None else 0.25,
            "iou_threshold": float(job["iou_threshold"]) if job["iou_threshold"] is not None else 0.45,
        },
        "metrics": {
            "tree_count": int(metrics["tree_count"]) if metrics else 0,
            "avg_confidence": float(metrics["avg_confidence"]) if metrics else 0.0,
            "duration_ms": int(metrics["duration_ms"]) if metrics else 0,
        },
        "detections": [
            {
                "id": int(d["id"]),
                "class_id": int(d["class_id"]),
                "class_name": str(d["class_name"]),
                "bbox": [float(d["x1"]), float(d["y1"]), float(d["x2"]), float(d["y2"])],
                "conf": float(d["confidence"]),
            }
            for d in detections
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def validate_upload(file: UploadFile, size_bytes: int) -> None:
    allowed_mime = {"image/jpeg", "image/png"}
    allowed_ext = {".jpg", ".jpeg", ".png"}
    ext = Path(file.filename or "").suffix.lower()

    if file.content_type not in allowed_mime or ext not in allowed_ext:
        raise HTTPException(status_code=415, detail="Only JPG and PNG files are allowed")

    if size_bytes <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if size_bytes > max_upload_bytes():
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds max size of {max_upload_bytes()} bytes",
        )


def validate_threshold(value: float, name: str) -> float:
    if value < 0 or value > 1:
        raise HTTPException(status_code=422, detail=f"{name} must be between 0 and 1")
    return float(value)


def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    conn = psycopg2.connect(database_url())
    try:
        yield conn
    finally:
        conn.close()


def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(redis_url(), decode_responses=True)


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Invalid email format")
    return normalized


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=jwt_expiry_minutes())).timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=jwt_algorithm())


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[jwt_algorithm()])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, email, full_name, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "api"}


@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: RegisterRequest,
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    email = validate_email(payload.email)
    password_hash = pwd_context.hash(payload.password)

    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO users(email, password_hash, full_name)
                    VALUES (%s, %s, %s)
                    RETURNING id, email
                    """,
                    (email, password_hash, payload.full_name),
                )
                user = cur.fetchone()
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")

    token = create_access_token(str(user["id"]), user["email"])
    return TokenResponse(access_token=token)


@app.post("/auth/login", response_model=TokenResponse)
def login_user(
    payload: LoginRequest,
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    email = validate_email(payload.email)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, email, password_hash FROM users WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()

    if not user or not pwd_context.verify(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user["id"]), user["email"])
    return TokenResponse(access_token=token)


@app.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, user_id, name, description, status, created_at, updated_at
            FROM projects
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (current_user["id"],),
        )
        rows = cur.fetchall()
    return rows


@app.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO projects(user_id, name, description, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING id, user_id, name, description, status, created_at, updated_at
                """,
                (current_user["id"], payload.name.strip(), payload.description),
            )
            project = cur.fetchone()
    return project


@app.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, user_id, name, description, status, created_at, updated_at
            FROM projects
            WHERE id = %s AND user_id = %s
            """,
            (str(project_id), current_user["id"]),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return row


@app.delete("/projects/{project_id}", response_model=DeleteResponse)
def delete_project(
    project_id: UUID,
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "DELETE FROM projects WHERE id = %s AND user_id = %s RETURNING id",
                (str(project_id), current_user["id"]),
            )
            deleted = cur.fetchone()

    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return DeleteResponse(deleted=True, id=deleted["id"])


@app.post("/projects/{project_id}/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_project_file(
    project_id: UUID,
    file: UploadFile = File(...),
    conf_threshold: float = Form(0.25),
    iou_threshold: float = Form(0.45),
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM projects WHERE id = %s AND user_id = %s",
            (str(project_id), current_user["id"]),
        )
        project = cur.fetchone()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = file.file.read()
    size_bytes = len(content)
    validate_upload(file, size_bytes)
    conf_threshold = validate_threshold(conf_threshold, "conf_threshold")
    iou_threshold = validate_threshold(iou_threshold, "iou_threshold")

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    generated_name = f"{uuid.uuid4().hex}{ext}"
    target = uploads_dir() / generated_name
    target.write_bytes(content)

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO jobs(project_id, status, input_type, conf_threshold, iou_threshold)
                VALUES (%s, 'queued', 'image', %s, %s)
                RETURNING id, status, conf_threshold, iou_threshold
                """,
                (str(project_id), conf_threshold, iou_threshold),
            )
            job = cur.fetchone()

            cur.execute(
                """
                INSERT INTO assets(project_id, job_id, kind, file_path, mime_type, size_bytes)
                VALUES (%s, %s, 'input', %s, %s, %s)
                RETURNING id
                """,
                (str(project_id), job["id"], str(target), file.content_type, size_bytes),
            )
            asset = cur.fetchone()

    queue = get_redis_client()
    try:
        queue.rpush(job_queue_key(), str(job["id"]))
    except Exception as exc:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'failed', error_message = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (f"Queue publish failed: {exc}", str(job["id"])),
                )
        raise HTTPException(status_code=503, detail="Failed to queue job")

    return UploadResponse(
        job_id=job["id"],
        asset_id=asset["id"],
        project_id=project_id,
        status=job["status"],
        file_path=str(target),
        mime_type=file.content_type or "",
        size_bytes=size_bytes,
        conf_threshold=float(job["conf_threshold"]),
        iou_threshold=float(job["iou_threshold"]),
    )


@app.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(
    job_id: UUID,
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        job = get_owned_job_or_404(cur, job_id, current_user["id"])
        metrics = fetch_job_metrics(cur, job_id)
        detections = fetch_job_detections(cur, job_id)
        assets = fetch_job_assets(cur, job_id)

    return JobDetailResponse(
        id=job["id"],
        project_id=job["project_id"],
        status=job["status"],
        input_type=job["input_type"],
        error_message=job["error_message"],
        conf_threshold=float(job["conf_threshold"]) if job["conf_threshold"] is not None else 0.25,
        iou_threshold=float(job["iou_threshold"]) if job["iou_threshold"] is not None else 0.45,
        started_at=job["started_at"],
        completed_at=job["completed_at"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        metrics=(
            JobMetricsResponse(
                tree_count=int(metrics["tree_count"]),
                avg_confidence=float(metrics["avg_confidence"]),
                duration_ms=int(metrics["duration_ms"]),
            )
            if metrics
            else None
        ),
        detections=detections,
        assets=JobAssetsResponse(
            input_image=assets["input_image"],
            annotated_image=assets["annotated_image"],
            csv_download_url=f"/jobs/{job_id}/download/csv",
            json_download_url=f"/jobs/{job_id}/download/json",
        ),
    )


@app.get("/jobs/{job_id}/download/csv")
def download_job_csv(
    job_id: UUID,
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        job = get_owned_job_or_404(cur, job_id, current_user["id"])
        detections = fetch_job_detections(cur, job_id)
        metrics = fetch_job_metrics(cur, job_id)

    target = csv_artifact_path(job_id)
    write_detections_csv(target, detections, metrics)

    return FileResponse(
        path=str(target),
        media_type="text/csv",
        filename=f"{job_id}_detections.csv",
        headers={"X-Artifact-Path": str(target), "X-Job-Status": job["status"]},
    )


@app.get("/jobs/{job_id}/download/json")
def download_job_json(
    job_id: UUID,
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        job = get_owned_job_or_404(cur, job_id, current_user["id"])
        detections = fetch_job_detections(cur, job_id)
        metrics = fetch_job_metrics(cur, job_id)

    target = json_artifact_path(job_id)
    write_detections_json(target, job, detections, metrics)

    return FileResponse(
        path=str(target),
        media_type="application/json",
        filename=f"{job_id}_detections.json",
        headers={"X-Artifact-Path": str(target), "X-Job-Status": job["status"]},
    )


@app.get("/jobs/{job_id}/annotated-image")
def get_job_annotated_image(
    job_id: UUID,
    current_user=Depends(get_current_user),
    conn: psycopg2.extensions.connection = Depends(get_conn),
):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        _ = get_owned_job_or_404(cur, job_id, current_user["id"])
        cur.execute(
            """
            SELECT file_path, mime_type
            FROM assets
            WHERE job_id = %s AND kind = 'annotated'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (str(job_id),),
        )
        asset = cur.fetchone()

    if not asset:
        raise HTTPException(status_code=404, detail="Annotated image not found")

    path = Path(asset["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Annotated image file missing on disk")

    media_type = asset["mime_type"] or "image/jpeg"
    filename = f"{job_id}_annotated{path.suffix or '.jpg'}"
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=filename,
        headers={"X-Artifact-Path": str(path)},
    )
