-- 001_init.sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',
    input_type TEXT NOT NULL DEFAULT 'image',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    mime_type TEXT,
    size_bytes BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS detections (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    class_id INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    x1 DOUBLE PRECISION NOT NULL,
    y1 DOUBLE PRECISION NOT NULL,
    x2 DOUBLE PRECISION NOT NULL,
    y2 DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tree_count INTEGER NOT NULL DEFAULT 0,
    avg_confidence DOUBLE PRECISION,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Required indexes: project_id, job_id, status, created_at
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

CREATE INDEX IF NOT EXISTS idx_jobs_project_id ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);

CREATE INDEX IF NOT EXISTS idx_assets_project_id ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_assets_job_id ON assets(job_id);
CREATE INDEX IF NOT EXISTS idx_assets_created_at ON assets(created_at);

CREATE INDEX IF NOT EXISTS idx_detections_job_id ON detections(job_id);
CREATE INDEX IF NOT EXISTS idx_detections_created_at ON detections(created_at);

CREATE INDEX IF NOT EXISTS idx_job_metrics_project_id ON job_metrics(project_id);
CREATE INDEX IF NOT EXISTS idx_job_metrics_job_id ON job_metrics(job_id);
CREATE INDEX IF NOT EXISTS idx_job_metrics_created_at ON job_metrics(created_at);

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
