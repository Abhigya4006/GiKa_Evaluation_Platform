# ACME Corp Finance & Compliance Benchmark (synthetic)

Synthetic benchmark that plugs into the GIKA Eval Platform's existing
ingestion + evaluation pipeline with **no schema changes**. Domain: internal
enterprise finance, compliance, procurement, and vendor management for a
fictitious multinational ("ACME Corp").

- **`dataset_id`**: `acme_finops_bench`
- **Queries**: 100 (24 easy · 43 medium · 33 hard, including 2 unanswerable)
- **Distinct GT documents**: 29 (policies, SOPs, matrices, registers)
- **Query types covered**: lookup, definition, temporal, numerical, comparative,
  single-hop, multi-hop, entity-centric

## Files

| File | What it is |
|---|---|
| `dataset.json` | Canonical `BenchmarkDataset` (schema: `app/schemas/dataset.py`). This is what the platform ingests. |
| `leaderboard.json` | Optional standalone leaderboard (same entries also inlined in `dataset.json`). |
| `corpus.json` | Metadata-only manifest of the referenced documents. The bundled `mock_local` retriever does **not** need this — it uses `doc_id`/`filename` from the ingested queries — but a real retrieval backend can use it to seed a realistic-looking corpus. |

## Schema conformance

Every item matches the canonical `DatasetItem` schema exactly:

```json
{
  "query_id": "acmf_qNNNN",
  "query": "...",
  "gt_answer": "...",
  "categories": ["lookup", "single-hop", "numerical", ...],
  "difficulty": "easy|medium|hard",
  "eval_label": "answerable|unanswerable",
  "gt_supporting_facts": [{"fact_id": "acmf_fNNNN", "text": "...", "doc_id": "doc_acme_..."}],
  "gt_documents": [{"doc_id": "doc_acme_...", "filename": "...", "page_numbers": [3, 7]}],
  "metadata": {"language": "en"}
}
```

All `query_id`s are prefixed `acmf_` and all `fact_id`s / `doc_id`s use the
`acmf_` / `doc_acme_` namespaces so they cannot collide with the platform's
built-in EU AI Act benchmark.

## Query composition

- **Domain coverage** — Delegation of Authority, Procurement, Vendor Onboarding
  & Risk, Sanctions/AML, Expenses, Travel, SOX, Revenue Recognition (ASC 606),
  Close Calendar, Chart of Accounts, CAPEX/OPEX, Budget & Forecast, Anti-Bribery
  & Corruption, Tax & VAT, Treasury & FX, AR/AP/Credit, Records Retention,
  Internal Audit, Enterprise Risk, KRIs, Whistleblowing, Data Privacy.
- **Difficulty gradient** — easy queries are single-fact lookups; medium queries
  span 1–2 facts and often two-hop reasoning; hard queries require 2–3 facts
  across multiple documents.
- **Unanswerable pair** — `acmf_q0097` and `acmf_q0098` test abstention
  behaviour (out-of-scope topics).
- **Comparative and multi-hop** examples deliberately span multiple documents
  (e.g. Delegation of Authority × Procurement × Vendor Risk) so document-recall
  and MRR/NDCG produce meaningful signal.

## Rebuild

```bash
python scripts/_build_synthetic_enterprise_dataset.py
```

Fully deterministic — every rebuild produces byte-identical `dataset.json`.

## Ingest and evaluate

```bash
# Ingest into the platform's DB (idempotent; safe to run over an existing DB).
python scripts/seed_sample_data.py --dataset data/synthetic_enterprise_bench/dataset.json

# Run against the bundled mock retriever, in-process.
python scripts/run_evaluation.py --dataset-id acme_finops_bench --local --export

# Or against your own retrieval API (canonical contract):
python scripts/run_evaluation.py \
    --dataset-id acme_finops_bench \
    --provider generic_http \
    --endpoint https://your-api.example.com/retrieve --export

# Or via the dashboard — Datasets tab shows both benchmarks side by side.
streamlit run app/dashboard.py
```

## Baseline leaderboard

Illustrative baseline scores are inlined in the dataset and duplicated in
`leaderboard.json`:

| System         | F1   | EM   | Recall | Doc Recall |
|----------------|------|------|--------|------------|
| BaselineRAG    | 0.68 | 0.51 | 0.72   | 0.65       |
| EnterpriseRAG  | 0.77 | 0.62 | 0.81   | 0.74       |

These are illustrative anchors so the dashboard's Leaderboard Comparison view
has content to render. Replace them with your own measurements as you generate
real runs.
