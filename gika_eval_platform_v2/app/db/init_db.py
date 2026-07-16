
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import repository

logger = get_logger(__name__)


def init_db(drop: bool = False) -> None:
    settings = get_settings()
    settings.ensure_dirs()

    try:
        from app.db import models  # noqa: F401
        from app.db.base import Base
        from app.db.session import engine

        if drop:
            logger.warning("Dropping all tables before re-creating (SQLAlchemy).")
            Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        # Also run the raw-SQL init so tables only defined in repository.SCHEMA_SQL
        # (e.g. dynamic_metric_results) and column migrations are applied.
        repository.init_schema()
        logger.info("Database initialized via SQLAlchemy at %s", settings.db_url)
    except Exception as exc:  # noqa: BLE001 - fall back to raw sqlite path
        logger.info("SQLAlchemy unavailable (%s); using raw-sqlite schema.", type(exc).__name__)
        if drop:
            import sqlite3
            conn = repository.connect()
            try:
                for tbl in (
                    "aggregated_results", "query_metrics", "api_responses",
                    "evaluation_runs", "leaderboard_entries", "supporting_documents",
                    "supporting_facts", "queries", "datasets",
                ):
                    conn.execute(f"DROP TABLE IF EXISTS {tbl}")
                conn.commit()
            finally:
                conn.close()
            _ = sqlite3
        repository.init_schema()
        logger.info("Database initialized via raw sqlite at %s", settings.db_url)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize GIKA eval DB.")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables first.")
    args = parser.parse_args()
    init_db(drop=args.drop)
