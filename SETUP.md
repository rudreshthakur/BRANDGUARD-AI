# Setup and deployment

## Prerequisites
- Python 3.11+ (tested on 3.13)
- Node.js 20+ (tested on 22)
- Optional: PostgreSQL 14+ (tested with the local server shipped in the dev environment). SQLite is used automatically if `DATABASE_URL` is unset.

## Local development

```bash
git clone <repo-url> brandguard && cd brandguard
cp .env.example .env              # optional; defaults work out of the box

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
# -> http://localhost:8000/api/health   http://localhost:8000/docs

# Frontend (new terminal)
cd frontend
npm install
npm run dev                        # -> http://localhost:5173  (proxies /api to :8000)
```

Tables are created automatically on startup. Clicking **Launch demo workspace** seeds a fresh synthetic Northstar Labs workspace through the real ingestion pipeline.

## Single-service production run

```bash
cd frontend && npm ci && npm run build      # outputs frontend/dist
cd ../backend && pip install -r requirements.txt
DATABASE_URL=postgresql://user:pass@host:5432/brandguard uvicorn app.main:app --host 0.0.0.0 --port 8000
```
FastAPI serves `frontend/dist` (SPA fallback included) and the API from the same origin.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/brandguard.db` | SQLAlchemy URL. `postgres://` and `postgresql://` are normalised to psycopg 3. |
| `BRANDGUARD_LLM_PROVIDER` | `none` | `none`, `anthropic`, `openai` (OpenAI-compatible) |
| `BRANDGUARD_LLM_API_KEY` | – | Provider key (server-side only) |
| `BRANDGUARD_LLM_MODEL` | provider default | Model name |
| `BRANDGUARD_LLM_BASE_URL` | provider default | Custom endpoint |
| `BRANDGUARD_LLM_TIMEOUT` | `25` | Seconds |
| `BRANDGUARD_MAX_UPLOAD_MB` | `10` | Document upload limit |
| `BRANDGUARD_MAX_CONTENT_CHARS` | `20000` | Submission length limit |
| `BRANDGUARD_SANDBOX_TTL_HOURS` | `72` | Demo workspace lifetime |
| `BRANDGUARD_DEMO_RATE_LIMIT` | `30` | Demo workspaces per IP per hour |
| `BRANDGUARD_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origins (split hosting only) |
| `BRANDGUARD_FRONTEND_DIST` | `../frontend/dist` | Built frontend location |
| `VITE_API_BASE` (frontend build) | same origin | API base URL when the frontend is hosted separately |

## Deploy option A: Render (recommended, one service + Postgres)

1. Push this repository to GitHub (public, so judges can read it).
2. In Render, choose **New → Blueprint** and select the repository. `render.yaml` creates:
   - `brandguard-ai`, a Docker web service (builds the frontend, serves API and UI), health check `/api/health`
   - `brandguard-db`, managed PostgreSQL wired to `DATABASE_URL`
3. Optional: set `BRANDGUARD_LLM_PROVIDER` and `BRANDGUARD_LLM_API_KEY` in the dashboard.
4. Open the service URL in a private window, click **Launch demo workspace**, and run the checklist in TESTING.md.

Notes (Render's free tier, per Render's docs): web services sleep after 15 minutes without traffic and take about a minute to wake, so open the URL shortly before judging. Free Render Postgres databases **expire 30 days after creation**, with a 14-day grace period before deletion; upgrade the database, or point `DATABASE_URL` at another Postgres, before then. To confirm which database is in use, open `/api/health` and check `database_backend`.

Current deployment: https://brandguard-ai-hndd.onrender.com (blueprint `brandguard-ai`, repo https://github.com/rudreshthakur/BRANDGUARD-AI, branch `main`).

## Deploy option B: Docker anywhere

```bash
docker build -t brandguard .
docker run -p 8000:8000 -e DATABASE_URL=postgresql://... brandguard
# without DATABASE_URL it uses SQLite at /data/brandguard.db (mount a volume for persistence)
```
*The Dockerfile was written but could not be built in our authoring environment (no Docker daemon). Its steps were verified individually: a clean venv install of requirements.txt, the production frontend build, and the full test suite on PostgreSQL.*

## Deploy option C: Vercel (frontend) + Render (API)

- Render: deploy as in option A. Set `BRANDGUARD_CORS_ORIGINS=https://<your-app>.vercel.app`.
- Vercel: import the repo with root directory `frontend`. Set `VITE_API_BASE=https://<render-service>.onrender.com`. `frontend/vercel.json` handles SPA rewrites.

## Tests

See [TESTING.md](TESTING.md). Quick commands:
```bash
cd backend && python -m pytest -q
cd frontend && npm run typecheck && npm test && npm run build
python e2e/test_judge_journey.py http://localhost:8000     # needs `pip install playwright && playwright install chromium`
```
