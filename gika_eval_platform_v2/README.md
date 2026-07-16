GIKA Evaluation Platform
A full-stack evaluation platform for benchmarking Retrieval-Augmented Generation (RAG) and enterprise search systems. The platform ingests benchmark datasets, executes evaluation runs against retrieval APIs or local mock providers, computes retrieval and answer quality metrics, and visualizes results through a React dashboard.
Features
Upload and manage benchmark datasets
Run evaluations using local mock or external retrieval APIs
Automatic metric computation (retrieval + answer quality)
Interactive analytics dashboard
Side-by-side comparison of evaluation runs
Export evaluation results
Extensible provider and metric architecture
Tech Stack
Backend: FastAPI, Python
Frontend: React, TypeScript, Vite
Database: SQLite
Testing: Pytest
Project Structure
```text
.
├── app/                # Backend application
├── frontend/           # React frontend
├── scripts/            # Utility scripts
├── tests/              # Test suite
├── data/               # Database and sample datasets
└── requirements.txt
```
Getting Started
Prerequisites
Python 3.10+
Node.js 18+
Backend
```bash
python -m venv .venv

# Windows
.\.venv\Scripts\activate

pip install -r requirements.txt
python scripts/seed_sample_data.py
uvicorn app.api.main:app --reload
```
Backend runs at http://127.0.0.1:8000
Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at http://localhost:5173
Running Tests
```bash
pytest tests -v
```
## API Overview

| Endpoint | Description |
|----------|-------------|
| `/api/datasets` | Dataset management |
| `/api/runs` | Create and manage evaluation runs |
| `/api/metrics` | Available evaluation metrics |
| `/api/compare` | Compare evaluation runs |
| `/api/exports` | Export results |

---

## Configuration

Environment variables:

| Variable | Purpose |
|----------|---------|
| `GIKA_DB_URL` | SQLite database location |
| `GIKA_RETRIEVAL_ENDPOINT` | Retrieval API endpoint |
| `GIKA_LLM_ENDPOINT` | LLM endpoint (optional) |
| `GIKA_LLM_API_KEY` | LLM API key (optional) |
| `VITE_API_BASE_URL` | Backend URL for the frontend |

---

## Deployment

- **Backend:** FastAPI (Uvicorn/Gunicorn)
- **Frontend:** Static build (`npm run build`)
- **Database:** SQLite (replaceable with another backend if required)

---
