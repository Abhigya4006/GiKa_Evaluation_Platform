# NovaCorp HR & People-Ops Benchmark (synthetic)

Synthetic benchmark that plugs into the GIKA Eval Platform's existing
ingestion + evaluation pipeline with **no schema changes**. Domain: internal HR,
people-operations, benefits, payroll, IT-for-employees, learning, and workplace
policies for a fictitious multinational ("NovaCorp Inc.").

Complements the existing benchmarks:

| Dataset | Domain | Queries |
|---|---|---|
| `eu_ai_act_bench` | Public regulation (EU AI Act) | 32 |
| `acme_finops_bench` | Enterprise finance & compliance (ACME) | 100 |
| **`novacorp_hr_bench`** | **Enterprise HR & people-ops (NovaCorp)** | **100** |

## Dataset stats

- **`dataset_id`**: `novacorp_hr_bench`
- **Queries**: 100 (32 easy · 35 medium · 33 hard, including 2 unanswerable)
- **Distinct GT documents**: 32 (handbook, benefits guides, PTO, remote/hybrid,
  compensation, equity, performance, IT, security, immigration, DEI, and more)
- **Query types covered**: lookup, definition, temporal, numerical,
  comparative, single-hop, multi-hop, entity-centric

## Files

| File | What it is |
|---|---|
| `dataset.json` | Canonical `BenchmarkDataset` (schema: `app/schemas/dataset.py`). |
| `leaderboard.json` | Optional standalone leaderboard (same entries also inlined in `dataset.json`). |
| `corpus.json` | Metadata-only manifest of the referenced documents. The bundled `mock_local` retriever does **not** need this — it uses `doc_id`/`filename` from the ingested queries — but a real retrieval backend can use it to seed a realistic-looking corpus. |

## Schema conformance

Every item matches the canonical `DatasetItem` schema exactly:

```json
{
  "query_id": "nvhr_qNNNN",
  "query": "...",
  "gt_answer": "...",
  "categories": ["lookup", "single-hop", "numerical", ...],
  "difficulty": "easy|medium|hard",
  "eval_label": "answerable|unanswerable",
  "gt_supporting_facts": [{"fact_id": "nvhr_fNNNN", "text": "...", "doc_id": "doc_nova_..."}],
  "gt_documents": [{"doc_id": "doc_nova_...", "filename": "...", "page_numbers": [3, 7]}],
  "metadata": {"language": "en"}
}
```

All `query_id`s are prefixed `nvhr_`, all `fact_id`s use `nvhr_`, and all
`doc_id`s use `doc_nova_` so they cannot collide with `eu_ai_act_bench` (uses
`q_NNNN` / `f_NNN` / `doc_eu_...`) or `acme_finops_bench` (uses `acmf_` /
`doc_acme_`).

## Query composition

- **Domain coverage** — PTO / leave types / parental leave, US/EU/India
  benefits, remote & hybrid work, compensation / bonus / equity, payroll and
  overtime, performance management and PIP, learning & development, employee
  referrals, IT acceptable-use / BYOD / security, DEI and ERGs, harassment,
  grievance, contractor engagement, immigration & relocation, wellness / EAP /
  workplace health & safety, and employee data privacy.
- **Difficulty gradient** — easy items are single-fact lookups; medium items
  span two facts or one two-hop reasoning step; hard items require 2–3 facts
  often crossing document boundaries (e.g. HR × Payroll, Benefits × Parental
  Leave, Immigration × Onboarding × Benefits).
- **Comparative examples** are woven throughout (US vs EU benefits, hybrid vs
  remote, employees vs contractors, primary vs secondary caregiver) so
  document-recall and NDCG produce meaningful signal.
- **Unanswerable pair** — `nvhr_q0097` and `nvhr_q0098` test abstention
  behaviour with plausibly-phrased out-of-scope questions.

## Rebuild

```bash
python scripts/_build_synthetic_hr_dataset.py
```

Fully deterministic — every rebuild produces byte-identical `dataset.json`.

## Ingest and evaluate

```bash
# Ingest into the platform's DB (idempotent; safe to run over an existing DB).
python scripts/seed_sample_data.py --dataset data/synthetic_hr_bench/dataset.json

# Run against the bundled mock retriever, in-process.
python scripts/run_evaluation.py --dataset-id novacorp_hr_bench --local --export

# Or against any HTTP endpoint following the canonical contract:
python scripts/run_evaluation.py \
    --dataset-id novacorp_hr_bench \
    --provider generic_http \
    --endpoint https://your-api.example.com/retrieve --export

# Or via the dashboard — Datasets tab lists all ingested benchmarks side by side.
streamlit run app/dashboard.py
```

## Baseline leaderboard

Illustrative baseline scores inlined in the dataset and duplicated in
`leaderboard.json`:

| System        | F1   | EM   | Recall | Doc Recall |
|---------------|------|------|--------|------------|
| BaselineRAG   | 0.66 | 0.48 | 0.70   | 0.64       |
| HR-RAG-v1     | 0.74 | 0.58 | 0.78   | 0.72       |

These are illustrative anchors so the dashboard's Leaderboard Comparison view
has content to render. Replace them with your own measurements as you generate
real runs.
