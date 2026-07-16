
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.core.config import get_settings
from app.core.utils import utcnow_iso

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT DEFAULT '1.0.0',
    domain TEXT DEFAULT 'generic',
    source TEXT DEFAULT 'internal-curated',
    metric_config_json TEXT DEFAULT '{}',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS queries (
    query_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    gt_answer TEXT DEFAULT '',
    -- V1: list of acceptable answers (JSON-serialized). MuSiQue-style
    -- multi-answer support (Directive Section 5.1 EM applies to any).
    gt_answers_json TEXT DEFAULT '[]',
    categories_json TEXT DEFAULT '[]',
    difficulty TEXT DEFAULT 'medium',
    eval_label TEXT DEFAULT 'answerable',
    metadata_json TEXT DEFAULT '{}',
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_queries_dataset ON queries(dataset_id);
CREATE INDEX IF NOT EXISTS ix_queries_difficulty ON queries(difficulty);

CREATE TABLE IF NOT EXISTS supporting_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT,
    query_id TEXT NOT NULL,
    fact_text TEXT DEFAULT '',
    doc_id TEXT,
    UNIQUE(query_id, fact_id),
    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_facts_query ON supporting_facts(query_id);

CREATE TABLE IF NOT EXISTS supporting_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT,
    query_id TEXT NOT NULL,
    filename TEXT,
    page_numbers_json TEXT DEFAULT '[]',
    UNIQUE(query_id, doc_id),
    FOREIGN KEY (query_id) REFERENCES queries(query_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_docs_query ON supporting_documents(query_id);

CREATE TABLE IF NOT EXISTS leaderboard_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    system_name TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    UNIQUE(dataset_id, system_name, metric),
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    dataset_version TEXT DEFAULT '',
    run_name TEXT DEFAULT '',
    provider TEXT DEFAULT 'generic_http',
    provider_config_json TEXT DEFAULT '{}',
    api_endpoint TEXT DEFAULT '',
    api_config_json TEXT DEFAULT '{}',
    metric_config_json TEXT DEFAULT '{}',
    selected_metrics_json TEXT DEFAULT '[]',
    comparison_group_id TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    total_queries INTEGER DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_runs_dataset ON evaluation_runs(dataset_id);
CREATE INDEX IF NOT EXISTS ix_runs_status ON evaluation_runs(status);

CREATE TABLE IF NOT EXISTS api_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    raw_payload_json TEXT DEFAULT '{}',
    raw_payload_path TEXT DEFAULT '',
    retrieval_time_ms INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ok',
    created_at TEXT,
    UNIQUE(run_id, query_id),
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_response_run_query ON api_responses(run_id, query_id);

CREATE TABLE IF NOT EXISTS query_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    -- V1 retrieval-side metrics.
    recall REAL DEFAULT 0.0,
    precision REAL DEFAULT 0.0,
    f1 REAL DEFAULT 0.0,
    document_recall REAL DEFAULT 0.0,
    -- V1 answer-side metrics.
    exact_match REAL DEFAULT 0.0,
    semantic_similarity REAL,
    llm_judge_score REAL,
    llm_judge_verdict TEXT,
    llm_judge_rationale TEXT,
    -- V1 answer-generation output (produced by the benchmarking module).
    generated_answer TEXT DEFAULT '',
    -- V1 classification.
    success INTEGER DEFAULT 0,
    failure_type TEXT DEFAULT 'success',
    metric_details_json TEXT DEFAULT '{}',
    -- Deferred columns (kept for back-compat; not written by V1).
    answerability_score REAL,
    mrr REAL DEFAULT 0.0,
    ndcg REAL DEFAULT 0.0,
    map_score REAL DEFAULT 0.0,
    recall_at_1 REAL DEFAULT 0.0,
    recall_at_3 REAL DEFAULT 0.0,
    recall_at_5 REAL DEFAULT 0.0,
    recall_at_10 REAL DEFAULT 0.0,
    UNIQUE(run_id, query_id),
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_metric_run_query ON query_metrics(run_id, query_id);
CREATE INDEX IF NOT EXISTS ix_metric_failure ON query_metrics(failure_type);

CREATE TABLE IF NOT EXISTS aggregated_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    scope_type TEXT,
    scope_value TEXT,
    metric_name TEXT,
    metric_value REAL DEFAULT 0.0,
    UNIQUE(run_id, scope_type, scope_value, metric_name),
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_agg_run_scope ON aggregated_results(run_id, scope_type);

CREATE TABLE IF NOT EXISTS dynamic_metric_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_metadata_json TEXT DEFAULT '{}',
    UNIQUE(run_id, query_id, metric_name),
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_dyn_metric_run ON dynamic_metric_results(run_id);
CREATE INDEX IF NOT EXISTS ix_dyn_metric_run_query ON dynamic_metric_results(run_id, query_id);
"""


def _db_path() -> str:
    url = get_settings().db_url
    if url.startswith("sqlite:///"):
        raw = url.replace("sqlite:///", "", 1)
    elif url.startswith("sqlite://"):
        raw = url.replace("sqlite://", "", 1)
    else:
        raw = url
    if raw == ":memory:" or raw == "":
        return ":memory:"
    p = Path(raw)
    if not p.is_absolute():
        p = get_settings().project_root / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA_SQL)
        _apply_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(evaluation_runs)")}
    if "provider" not in existing:
        conn.execute("ALTER TABLE evaluation_runs ADD COLUMN provider TEXT DEFAULT 'generic_http'")
    if "provider_config_json" not in existing:
        conn.execute("ALTER TABLE evaluation_runs ADD COLUMN provider_config_json TEXT DEFAULT '{}'")
    if "run_name" not in existing:
        conn.execute("ALTER TABLE evaluation_runs ADD COLUMN run_name TEXT DEFAULT ''")

    # V1: queries.gt_answers_json (list of acceptable answers).
    q_cols = {row["name"] for row in conn.execute("PRAGMA table_info(queries)")}
    if "gt_answers_json" not in q_cols:
        conn.execute("ALTER TABLE queries ADD COLUMN gt_answers_json TEXT DEFAULT '[]'")

    # query_metrics: generated_answer + V1 LLM judge columns.
    qm_cols = {row["name"] for row in conn.execute("PRAGMA table_info(query_metrics)")}
    if "generated_answer" not in qm_cols:
        conn.execute("ALTER TABLE query_metrics ADD COLUMN generated_answer TEXT DEFAULT ''")
    if "llm_judge_score" not in qm_cols:
        conn.execute("ALTER TABLE query_metrics ADD COLUMN llm_judge_score REAL")
    if "llm_judge_verdict" not in qm_cols:
        conn.execute("ALTER TABLE query_metrics ADD COLUMN llm_judge_verdict TEXT")
    if "llm_judge_rationale" not in qm_cols:
        conn.execute("ALTER TABLE query_metrics ADD COLUMN llm_judge_rationale TEXT")

    # V2: selected_metrics_json + comparison_group_id on evaluation_runs.
    if "selected_metrics_json" not in existing:
        conn.execute("ALTER TABLE evaluation_runs ADD COLUMN selected_metrics_json TEXT DEFAULT '[]'")
    if "comparison_group_id" not in existing:
        conn.execute("ALTER TABLE evaluation_runs ADD COLUMN comparison_group_id TEXT DEFAULT ''")


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------- #
# Dataset ingestion
# --------------------------------------------------------------------------- #

def upsert_dataset(ds: Dict[str, Any]) -> None:
    conn = connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO datasets
               (dataset_id, name, version, domain, source, metric_config_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                ds["dataset_id"], ds["name"], ds.get("version", "1.0.0"),
                ds.get("domain", "generic"), ds.get("source", "internal-curated"),
                _j(ds.get("metric_config", {})), utcnow_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_query(q: Dict[str, Any], dataset_id: str) -> None:
    conn = connect()
    try:
        # Guard against cross-dataset query_id collisions. queries.query_id is
        # a global primary key today; without this check, uploading a second
        # dataset that reuses an existing query_id would silently overwrite the
        # first dataset's row and orphan its facts / documents / responses.
        row = conn.execute(
            "SELECT dataset_id FROM queries WHERE query_id=?", (q["query_id"],)
        ).fetchone()
        if row is not None and row["dataset_id"] != dataset_id:
            raise ValueError(
                f"query_id '{q['query_id']}' is already used by dataset "
                f"'{row['dataset_id']}'. Choose unique query_ids per dataset "
                "(the CSV loader auto-namespaces missing ones with the dataset_id)."
            )

        conn.execute(
            """INSERT OR REPLACE INTO queries
               (query_id, dataset_id, query_text, gt_answer, gt_answers_json,
                categories_json, difficulty, eval_label, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                q["query_id"], dataset_id, q["query"], q.get("gt_answer", ""),
                _j(q.get("gt_answers", []) or ([q["gt_answer"]] if q.get("gt_answer") else [])),
                _j(q.get("categories", [])), q.get("difficulty", "medium"),
                q.get("eval_label", "answerable"), _j(q.get("metadata", {})),
            ),
        )
        # Replace facts/docs for idempotency.
        conn.execute("DELETE FROM supporting_facts WHERE query_id=?", (q["query_id"],))
        for f in q.get("gt_supporting_facts", []):
            conn.execute(
                """INSERT OR REPLACE INTO supporting_facts
                   (fact_id, query_id, fact_text, doc_id) VALUES (?, ?, ?, ?)""",
                (f.get("fact_id"), q["query_id"], f.get("text", ""), f.get("doc_id")),
            )
        conn.execute("DELETE FROM supporting_documents WHERE query_id=?", (q["query_id"],))
        for d in q.get("gt_documents", []):
            conn.execute(
                """INSERT OR REPLACE INTO supporting_documents
                   (doc_id, query_id, filename, page_numbers_json) VALUES (?, ?, ?, ?)""",
                (d.get("doc_id"), q["query_id"], d.get("filename"),
                 _j(d.get("page_numbers", []))),
            )
        conn.commit()
    finally:
        conn.close()


def replace_leaderboard(dataset_id: str, entries: Iterable[Dict[str, Any]]) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM leaderboard_entries WHERE dataset_id=?", (dataset_id,))
        for e in entries:
            conn.execute(
                """INSERT OR REPLACE INTO leaderboard_entries
                   (dataset_id, system_name, metric, value) VALUES (?, ?, ?, ?)""",
                (dataset_id, e["system_name"], e["metric"], float(e["value"])),
            )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Reads used by evaluation + dashboard
# --------------------------------------------------------------------------- #

def get_dataset(dataset_id: str) -> Optional[Dict[str, Any]]:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM datasets WHERE dataset_id=?", (dataset_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_datasets() -> List[Dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_queries(dataset_id: str) -> List[Dict[str, Any]]:
    conn = connect()
    try:
        qrows = conn.execute(
            "SELECT * FROM queries WHERE dataset_id=? ORDER BY query_id", (dataset_id,)
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for qr in qrows:
            q = dict(qr)
            q["categories"] = json.loads(q.pop("categories_json") or "[]")
            q["metadata"] = json.loads(q.pop("metadata_json") or "{}")
            q["gt_answers"] = json.loads(q.pop("gt_answers_json", None) or "[]")
            if not q["gt_answers"] and q.get("gt_answer"):
                q["gt_answers"] = [q["gt_answer"]]
            facts = conn.execute(
                "SELECT fact_id, fact_text, doc_id FROM supporting_facts WHERE query_id=?",
                (q["query_id"],),
            ).fetchall()
            q["gt_supporting_facts"] = [
                {"fact_id": f["fact_id"], "text": f["fact_text"], "doc_id": f["doc_id"]}
                for f in facts
            ]
            docs = conn.execute(
                "SELECT doc_id, filename, page_numbers_json FROM supporting_documents WHERE query_id=?",
                (q["query_id"],),
            ).fetchall()
            q["gt_documents"] = [
                {"doc_id": d["doc_id"], "filename": d["filename"],
                 "page_numbers": json.loads(d["page_numbers_json"] or "[]")}
                for d in docs
            ]
            out.append(q)
        return out
    finally:
        conn.close()


def get_query(query_id: str) -> Optional[Dict[str, Any]]:
    conn = connect()
    try:
        qr = conn.execute("SELECT * FROM queries WHERE query_id=?", (query_id,)).fetchone()
        if not qr:
            return None
        q = dict(qr)
        q["categories"] = json.loads(q.pop("categories_json") or "[]")
        q["metadata"] = json.loads(q.pop("metadata_json") or "{}")
        q["gt_answers"] = json.loads(q.pop("gt_answers_json", None) or "[]")
        if not q["gt_answers"] and q.get("gt_answer"):
            q["gt_answers"] = [q["gt_answer"]]
        facts = conn.execute(
            "SELECT fact_id, fact_text, doc_id FROM supporting_facts WHERE query_id=?", (query_id,)
        ).fetchall()
        q["gt_supporting_facts"] = [
            {"fact_id": f["fact_id"], "text": f["fact_text"], "doc_id": f["doc_id"]} for f in facts
        ]
        docs = conn.execute(
            "SELECT doc_id, filename, page_numbers_json FROM supporting_documents WHERE query_id=?",
            (query_id,),
        ).fetchall()
        q["gt_documents"] = [
            {"doc_id": d["doc_id"], "filename": d["filename"],
             "page_numbers": json.loads(d["page_numbers_json"] or "[]")} for d in docs
        ]
        return q
    finally:
        conn.close()


def get_leaderboard(dataset_id: str) -> List[Dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT system_name, metric, value FROM leaderboard_entries WHERE dataset_id=?",
            (dataset_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #

def create_run(run: Dict[str, Any]) -> None:
    conn = connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO evaluation_runs
               (run_id, dataset_id, dataset_version, run_name,
                provider, provider_config_json,
                api_endpoint, api_config_json, metric_config_json,
                selected_metrics_json, comparison_group_id,
                status, total_queries, started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run["run_id"], run["dataset_id"], run.get("dataset_version", ""),
                run.get("run_name", ""),
                run.get("provider", "generic_http"),
                _j(run.get("provider_config", {})),
                run.get("api_endpoint", ""),
                _j(run.get("api_config", {})), _j(run.get("metric_config", {})),
                _j(run.get("selected_metrics", [])),
                run.get("comparison_group_id", ""),
                run.get("status", "pending"), int(run.get("total_queries", 0)),
                run.get("started_at"), run.get("finished_at"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_run_status(run_id: str, status: str, finished_at: Optional[str] = None) -> None:
    conn = connect()
    try:
        if finished_at is not None:
            conn.execute(
                "UPDATE evaluation_runs SET status=?, finished_at=? WHERE run_id=?",
                (status, finished_at, run_id),
            )
        else:
            conn.execute("UPDATE evaluation_runs SET status=? WHERE run_id=?", (status, run_id))
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM evaluation_runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_runs() -> List[Dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM evaluation_runs ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Responses (idempotent by run_id, query_id)
# --------------------------------------------------------------------------- #

def upsert_response(rec: Dict[str, Any]) -> None:
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO api_responses
               (run_id, query_id, raw_payload_json, raw_payload_path,
                retrieval_time_ms, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(run_id, query_id) DO UPDATE SET
                 raw_payload_json=excluded.raw_payload_json,
                 raw_payload_path=excluded.raw_payload_path,
                 retrieval_time_ms=excluded.retrieval_time_ms,
                 status=excluded.status,
                 created_at=excluded.created_at""",
            (
                rec["run_id"], rec["query_id"], _j(rec.get("raw_payload", {})),
                rec.get("raw_payload_path", ""), int(rec.get("retrieval_time_ms", 0)),
                rec.get("status", "ok"), utcnow_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_response(run_id: str, query_id: str) -> Optional[Dict[str, Any]]:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM api_responses WHERE run_id=? AND query_id=?", (run_id, query_id)
        ).fetchone()
        if not row:
            return None
        rec = dict(row)
        rec["raw_payload"] = json.loads(rec.get("raw_payload_json") or "{}")
        return rec
    finally:
        conn.close()


def stored_query_ids(run_id: str) -> List[str]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT query_id FROM api_responses WHERE run_id=? AND status='ok'", (run_id,)
        ).fetchall()
        return [r["query_id"] for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Metrics + aggregates
# --------------------------------------------------------------------------- #

def upsert_query_metric(m: Dict[str, Any]) -> None:
    cols = [
        "run_id", "query_id",
        # V1 retrieval-side metrics.
        "recall", "precision", "f1", "document_recall",
        # V1 answer-side metrics.
        "exact_match", "semantic_similarity",
        "llm_judge_score", "llm_judge_verdict", "llm_judge_rationale",
        # V1 answer-generation output.
        "generated_answer",
        # Classification.
        "success", "failure_type", "metric_details_json",
    ]
    vals = [
        m["run_id"], m["query_id"],
        m.get("recall", 0.0), m.get("precision", 0.0),
        m.get("f1", 0.0), m.get("document_recall", 0.0),
        m.get("exact_match", 0.0), m.get("semantic_similarity"),
        m.get("llm_judge_score"), m.get("llm_judge_verdict"), m.get("llm_judge_rationale"),
        m.get("generated_answer", ""),
        1 if m.get("success") else 0,
        m.get("failure_type", "success"), _j(m.get("metric_details", {})),
    ]
    placeholders = ", ".join("?" for _ in cols)
    update_clause = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in ("run_id", "query_id"))
    conn = connect()
    try:
        conn.execute(
            f"""INSERT INTO query_metrics ({', '.join(cols)}) VALUES ({placeholders})
                ON CONFLICT(run_id, query_id) DO UPDATE SET {update_clause}""",
            vals,
        )
        conn.commit()
    finally:
        conn.close()


def get_query_metrics(run_id: str) -> List[Dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM query_metrics WHERE run_id=? ORDER BY query_id", (run_id,)
        ).fetchall()
        out = []
        for r in rows:
            rec = dict(r)
            rec["success"] = bool(rec["success"])
            rec["metric_details"] = json.loads(rec.get("metric_details_json") or "{}")
            out.append(rec)
        return out
    finally:
        conn.close()


def get_query_metric(run_id: str, query_id: str) -> Optional[Dict[str, Any]]:
    conn = connect()
    try:
        r = conn.execute(
            "SELECT * FROM query_metrics WHERE run_id=? AND query_id=?", (run_id, query_id)
        ).fetchone()
        if not r:
            return None
        rec = dict(r)
        rec["success"] = bool(rec["success"])
        rec["metric_details"] = json.loads(rec.get("metric_details_json") or "{}")
        return rec
    finally:
        conn.close()


def replace_aggregates(run_id: str, rows: Iterable[Dict[str, Any]]) -> None:
    conn = connect()
    try:
        conn.execute("DELETE FROM aggregated_results WHERE run_id=?", (run_id,))
        for a in rows:
            conn.execute(
                """INSERT OR REPLACE INTO aggregated_results
                   (run_id, scope_type, scope_value, metric_name, metric_value)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, a["scope_type"], a["scope_value"], a["metric_name"],
                 float(a["metric_value"])),
            )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Dynamic metric results (V2)
# --------------------------------------------------------------------------- #

def upsert_dynamic_metric(run_id: str, query_id: str, metric_name: str,
                          metric_value: Optional[float],
                          metric_metadata: Optional[Dict[str, Any]] = None) -> None:
    conn = connect()
    try:
        conn.execute(
            """INSERT INTO dynamic_metric_results
               (run_id, query_id, metric_name, metric_value, metric_metadata_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(run_id, query_id, metric_name) DO UPDATE SET
                 metric_value=excluded.metric_value,
                 metric_metadata_json=excluded.metric_metadata_json""",
            (run_id, query_id, metric_name, metric_value, _j(metric_metadata or {})),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_dynamic_metrics_batch(rows: List[Dict[str, Any]]) -> None:
    conn = connect()
    try:
        for row in rows:
            conn.execute(
                """INSERT INTO dynamic_metric_results
                   (run_id, query_id, metric_name, metric_value, metric_metadata_json)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(run_id, query_id, metric_name) DO UPDATE SET
                     metric_value=excluded.metric_value,
                     metric_metadata_json=excluded.metric_metadata_json""",
                (row["run_id"], row["query_id"], row["metric_name"],
                 row.get("metric_value"), _j(row.get("metric_metadata", {}))),
            )
        conn.commit()
    finally:
        conn.close()


def get_dynamic_metrics(run_id: str, query_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = connect()
    try:
        if query_id:
            rows = conn.execute(
                "SELECT * FROM dynamic_metric_results WHERE run_id=? AND query_id=? ORDER BY metric_name",
                (run_id, query_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM dynamic_metric_results WHERE run_id=? ORDER BY query_id, metric_name",
                (run_id,),
            ).fetchall()
        out = []
        for r in rows:
            rec = dict(r)
            rec["metric_metadata"] = json.loads(rec.get("metric_metadata_json") or "{}")
            out.append(rec)
        return out
    finally:
        conn.close()


def get_dynamic_metrics_for_query(run_id: str, query_id: str) -> Dict[str, Any]:
    rows = get_dynamic_metrics(run_id, query_id)
    return {r["metric_name"]: r["metric_value"] for r in rows}


def get_runs_by_comparison_group(group_id: str) -> List[Dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM evaluation_runs WHERE comparison_group_id=? ORDER BY started_at",
            (group_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_aggregates(run_id: str, scope_type: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = connect()
    try:
        if scope_type:
            rows = conn.execute(
                "SELECT * FROM aggregated_results WHERE run_id=? AND scope_type=?",
                (run_id, scope_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM aggregated_results WHERE run_id=?", (run_id,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
