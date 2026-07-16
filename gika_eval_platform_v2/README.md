# GIKA Dataset Evaluation & Analytics Platform (V2)

An offline-runnable platform that ingests a benchmark dataset, runs evaluation
against a retrieval API (or a built-in mock), generates final answers via a
benchmarking module, evaluates them with an LLM-as-Judge alongside deterministic
retrieval metrics, and serves a **React dashboard** backed by a **FastAPI REST API**.

The legacy Streamlit dashboard remains available for backward compatibility.

---

## Architecture

```
React Frontend (Vite + TypeScript)
       ↓  REST / JSON
FastAPI Backend (app/api/)
       ↓
Existing service layer:
  ├── ingestion (parse, validate, adapters, CSV, GT merge)
  ├── metric registry (V2, extensible)
  ├── evaluation runner (provider → retrieve → metrics → aggregate)
  ├── analytics service
  ├── export service
  ├── leaderboard service
  └── SQLite repository
       ↓
GIKA or other retrieval APIs (or mock_local)
```

### Key directories

| Directory | Purpose |
|---|---|
| `app/api/` | FastAPI application and REST route modules |
| `app/services/` | Business logic (run_service, analytics_service, etc.) |
| `app/evaluation/` | Evaluation runner, executor, analytics, checkpoint |
| `app/metrics/` | Metric implementations and V2 metric registry |
| `app/ingestion/` | Dataset parsing, validation, adapters, GT merge |
| `app/db/` | SQLite repository, schema, migrations |
| `app/api_client/` | Provider abstraction (mock_local, generic_http, gika_retrieve) |
| `frontend/` | React application (Vite + TypeScript + React Router) |
| `tests/` | pytest test suite |

---

## Quick start — V2 with React + FastAPI (mock mode, no external API needed)

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm

### 1. Backend setup

```powershell
# From the project root:
cd gika_eval_platform_v2

# Create virtual environment (recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Seed the sample dataset into the database
python scripts/seed_sample_data.py

# Start the FastAPI server
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend API is available at: **http://127.0.0.1:8000**
API docs (Swagger): **http://127.0.0.1:8000/docs**

### 2. Frontend setup

Open a **second terminal**:

```powershell
cd gika_eval_platform_v2/frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The React frontend is available at: **http://localhost:5173**

### 3. Use the application

1. Open http://localhost:5173 in your browser.
2. Go to **Datasets** → upload a benchmark file or verify the seeded sample.
3. Go to **New Run** → select a dataset, enable "local mock", click **Run Evaluation**.
4. Go to **Analytics** → click the completed run to see full analytics.
5. Go to **Compare** → configure two systems (both can use local mock) and run.

---

## Streamlit dashboard (legacy)

The Streamlit dashboard still works for backward compatibility:

```powershell
streamlit run app/dashboard.py
```

Available at: **http://localhost:8501**

---

## Running tests

```powershell
# Run all tests (existing + new API tests)
python -m pytest tests/ -v

# Run only API route tests
python -m pytest tests/test_api_routes.py -v
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/datasets` | List all ingested datasets |
| `GET` | `/api/datasets/{id}` | Get a single dataset |
| `GET` | `/api/datasets/{id}/queries` | Get queries for a dataset |
| `POST` | `/api/datasets/upload` | Upload & parse a benchmark file |
| `POST` | `/api/datasets/gt-merge` | Merge ground-truth into a parsed dataset |
| `POST` | `/api/datasets/ingest` | Ingest a parsed dataset into the DB |
| `DELETE` | `/api/datasets/{id}` | Delete a dataset |
| `GET` | `/api/metrics` | List all registered metrics |
| `GET` | `/api/metrics/by-category/{cat}` | Metrics filtered by category |
| `GET` | `/api/runs` | List all evaluation runs |
| `GET` | `/api/runs/providers` | Available retrieval providers |
| `POST` | `/api/runs` | Create a new run |
| `POST` | `/api/runs/{id}/execute` | Execute a pending run |
| `GET` | `/api/runs/{id}` | Get run metadata |
| `GET` | `/api/runs/{id}/dashboard` | Full analytics data for a run |
| `GET` | `/api/runs/{id}/queries/{qid}` | Query-level detail with metrics |
| `GET` | `/api/runs/{id}/compare/{other}` | Compare two runs |
| `POST` | `/api/compare` | Run side-by-side comparison |
| `GET` | `/api/compare/groups` | List historical comparison groups |
| `POST` | `/api/exports/{id}` | Export run results to files |

---

## Environment Variables

### Backend

| Variable | Default | Description |
|---|---|---|
| `GIKA_DB_URL` | `sqlite:///./data/gika_eval.db` | Database URL |
| `GIKA_CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |
| `GIKA_RETRIEVAL_ENDPOINT` | `http://127.0.0.1:8000/retrieve` | Default retrieval API endpoint |
| `GIKA_LLM_ENDPOINT` | (empty) | LLM endpoint for judge/generator |
| `GIKA_LLM_API_KEY` | (empty) | LLM API key (never exposed to frontend) |

### Frontend

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend API base URL |

---

## Deployment

For production deployment, the React frontend and FastAPI backend are served separately:

### Backend

```bash
# Build and serve with uvicorn (or gunicorn with uvicorn workers)
pip install -r requirements.txt
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Set `GIKA_CORS_ORIGINS` to include the frontend's production domain.

### Frontend

```bash
cd frontend
npm install
npm run build
# The build output is in frontend/dist/
# Serve with nginx, Caddy, or any static file server
```

Configure the frontend's `VITE_API_BASE_URL` at build time to point to the
production backend URL:

```bash
VITE_API_BASE_URL=https://api.your-domain.com npm run build
```

### Typical production setup

1. **Backend** on a VM or container, behind a reverse proxy (nginx/Caddy).
2. **Frontend** served as static files from CDN or the same reverse proxy.
3. The reverse proxy handles TLS and routes `/api/*` to the backend,
   everything else to the frontend's `dist/index.html`.

---

## Mock mode vs real GIKA credentials

### Works with mock_local (no credentials needed):

- Dataset upload, parsing, validation, and ingestion
- Capability analysis and ground-truth merge
- Evaluation runs using the `mock_local` provider
- All analytics, per-query results, failure taxonomy
- Side-by-side comparison (both systems as mock_local)
- Historical run persistence and exports
- Metric registry browsing and selection
- All dashboard visualizations

### Requires real API credentials:

- Evaluation runs using `generic_http` or `gika_retrieve` providers
  (these make HTTP calls to the configured retrieval endpoint)
- LLM-based answer generation (requires `GIKA_LLM_ENDPOINT` + `GIKA_LLM_API_KEY`)
- LLM-as-Judge scoring (falls back to `HeuristicJudge` when LLM is unavailable)

---

## V1/V2 feature table

| | Active | Deferred |
|---|---|---|
| **Retrieval metrics** | Recall · Precision · F1 · Document Recall | Recall@K · MRR · NDCG · MAP |
| **Answer metrics** | Exact Match · Semantic Similarity · LLM Judge · Token Overlap | Answerability |
| **Providers** | mock_local · generic_http · gika_retrieve | Additional providers via adapter |
| **Ingestion** | Native JSON · MuSiQue · HotpotQA · CSV (two layouts) | Additional adapters |
| **Frontend** | React (primary) · Streamlit (legacy) | — |
