# Tree Counting SaaS Monorepo

## Services
- frontend (Next.js)
- api (FastAPI)
- worker (Python worker)
- postgres
- redis

## Local run (without Docker)
- API: `python -m uvicorn app.main:app --reload --port 8000` from `api`
- Frontend: `npm run dev` from `frontend`
- Worker: `python app/worker.py` from `worker`

## Docker Compose
- `docker compose up --build`
