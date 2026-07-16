"""
FastAPI application – the REST back-end consumed by the React frontend.

All business logic is delegated to the existing service / repository layers;
routes are thin wrappers that translate HTTP ↔ service calls.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.init_db import init_db

from app.api.routes import datasets, runs, metrics, compare, exports

# Initialise the database (idempotent – safe on every startup).
init_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GIKA Evaluation Platform API",
        version="2.0.0",
        description="REST API for the GIKA RAG evaluation and benchmarking platform.",
    )

    # --- CORS -------------------------------------------------------------- #
    allowed_origins = os.getenv(
        "GIKA_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ----------------------------------------------------------- #
    app.include_router(datasets.router, prefix="/api/datasets", tags=["Datasets"])
    app.include_router(runs.router, prefix="/api/runs", tags=["Runs"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
    app.include_router(compare.router, prefix="/api/compare", tags=["Compare"])
    app.include_router(exports.router, prefix="/api/exports", tags=["Exports"])

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
