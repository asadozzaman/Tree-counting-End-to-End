import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional
from uuid import UUID
import uuid

import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
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


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value


def jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-only-secret-change-me")


def jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def jwt_expiry_minutes() -> int:
    return int(os.getenv("JWT_EXPIRE_MINUTES", "120"))


def max_upload_bytes() -> int:
    return int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))


def uploads_dir() -> Path:
    root = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
    root.mkdir(parents=True, exist_ok=True)
    return root


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


def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    conn = psycopg2.connect(database_url())
    try:
        yield conn
    finally:
        conn.close()


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

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    generated_name = f"{uuid.uuid4().hex}{ext}"
    target = uploads_dir() / generated_name
    target.write_bytes(content)

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO jobs(project_id, status, input_type)
                VALUES (%s, 'queued', 'image')
                RETURNING id, status
                """,
                (str(project_id),),
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

    return UploadResponse(
        job_id=job["id"],
        asset_id=asset["id"],
        project_id=project_id,
        status=job["status"],
        file_path=str(target),
        mime_type=file.content_type or "",
        size_bytes=size_bytes,
    )
