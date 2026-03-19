# Tree Counting SaaS (Full Project Guide)

End-to-end SaaS project for tree detection/counting with:
- **Next.js frontend** (login/register, projects, upload, jobs table, result detail)
- **FastAPI backend** (auth, projects, uploads, jobs, artifact downloads)
- **Worker service** (YOLO inference queue consumer)
- **PostgreSQL** (app data)
- **Redis** (job queue)

Model used by worker:
- `tree_yolo26s_best.pt`

---

## 1. What This Project Does

You can:
1. Register/login
2. Create projects
3. Upload JPG/PNG images
4. Queue inference jobs
5. Track job status (`queued -> running -> done/failed`)
6. View result details (tree count, confidence, duration)
7. Download results as CSV/JSON
8. View annotated output image

---

## 2. Tech Stack

- Frontend: Next.js 14 (App Router, TypeScript)
- API: FastAPI + PostgreSQL + Redis
- Worker: Python + Ultralytics YOLO
- Infra: Docker Compose

---

## 3. Project Structure

```text
frontend/   # Next.js UI
api/        # FastAPI app + migrations + tests + scripts
worker/     # Inference worker + metrics tests
docker-compose.yml
tree_yolo26s_best.pt
```

---

## 4. GitHub Setup and Clone

Repository URL:
- `https://github.com/asadozzaman/Tree-counting-End-to-End.git`

### A) Clone from GitHub (normal use)

```bash
git clone https://github.com/asadozzaman/Tree-counting-End-to-End.git
cd Tree-counting-End-to-End
```

### B) First-time: push this local project to GitHub

1. Create an empty GitHub repo in your account.
2. In local project root:

```bash
git init
git add .
git commit -m "Initial commit: Tree Counting SaaS"
git branch -M main
git remote add origin https://github.com/asadozzaman/Tree-counting-End-to-End.git
git push -u origin main
```

After this, anyone can clone with the command in section A.

---

## 5. Prerequisites

- Git
- Docker Desktop (with Compose)

Optional for non-Docker local run:
- Python 3.12+
- Node.js 20+

---

## 6. Environment Variables

Current examples are already included:
- `api/.env.example`
- `worker/.env.example`
- `frontend/.env.example`

Defaults are already wired for Docker Compose.

Important:
- Worker model path is `/models/tree_yolo26s_best.pt`
- Compose mounts root model file:
  - `./tree_yolo26s_best.pt:/models/tree_yolo26s_best.pt:ro`

---

## 7. Run with Docker (Recommended)

From repo root:

```bash
docker compose up -d --build
```

Services:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Check status:

```bash
docker compose ps
```

---

## 8. Database Setup (Migrations + Seed + Sanity)

Apply migrations:

```bash
docker compose exec -T api python scripts/apply_migrations.py
```

Seed sample data:

```bash
docker compose exec -T api python scripts/seed_data.py
```

Sanity checks:

```bash
docker compose exec -T api python scripts/db_sanity.py
```

---

## 9. Run Tests

API tests:

```bash
docker compose exec -T api python -m pytest -q
```

Worker unit tests:

```bash
docker compose exec -T worker python -m pytest -q tests/test_metrics.py
```

Frontend production build check (one-off container):

```bash
docker compose run --rm frontend npm run build
```

---

## 10. UI Workflow

1. Open http://localhost:3000
2. Register or login
3. Create a project
4. Open Upload page for that project
5. Upload image + thresholds (`conf`, `iou`)
6. Open Jobs table
7. Open result detail page
8. Download CSV/JSON and view annotated image

Note:
- Jobs table tracks job IDs in browser local storage for that project.

---

## 11. Key API Endpoints

Auth:
- `POST /auth/register`
- `POST /auth/login`

Projects:
- `GET /projects`
- `POST /projects`
- `GET /projects/{id}`
- `DELETE /projects/{id}`

Upload + Jobs:
- `POST /projects/{id}/upload`
- `GET /jobs/{id}`
- `GET /jobs/{id}/download/csv`
- `GET /jobs/{id}/download/json`
- `GET /jobs/{id}/annotated-image`

---

## 12. Artifacts and Outputs

Generated artifacts are stored under shared volume paths like:
- `/shared/uploads/artifacts/<job_id>_detections.csv`
- `/shared/uploads/artifacts/<job_id>_detections.json`
- `/shared/uploads/artifacts/<job_id>_annotated.jpg`

---

## 13. Useful Smoke Scripts

Run from API container:

```bash
python scripts/inference_samples.py
python scripts/jobs_artifacts_smoke.py
```

These verify queue processing, job completion, and downloadable artifacts.

---

## 14. Troubleshooting

- If frontend behaves strangely after route/file changes, restart frontend:

```bash
docker compose restart frontend
```

- If worker is slow to start after restart:
  - It installs OS libs at startup (current compose command), so initial boot may take time.

- If model load fails:
  - Ensure `tree_yolo26s_best.pt` exists in repo root.

---

## 15. Local Run Without Docker (Optional)

From each service directory:

- API:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

- Worker:
```bash
python -m app.worker
```

- Frontend:
```bash
npm run dev
```

You must run PostgreSQL + Redis separately and set env vars accordingly.
