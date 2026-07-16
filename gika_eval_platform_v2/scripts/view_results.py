
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse

from app.db import repository
from app.db.init_db import init_db


def list_runs():
    runs = repository.list_runs()
    if not runs:
        print("No evaluation runs found.")
        return
    print(f"\n{'='*80}")
    print(f"{'RUN ID':<40} {'DATASET':<25} {'STATUS':<12} {'QUERIES'}")
    print(f"{'='*80}")
    for r in runs:
        print(f"{r['run_id']:<40} {r['dataset_id']:<25} {r['status']:<12} {r['total_queries']}")
    print()


def show_run_summary(run_id: str):
    run = repository.get_run(run_id)
    if not run:
        print(f"Run not found: {run_id}")
        return

    print(f"\n{'='*80}")
    print(f"  RUN SUMMARY: {run_id}")
    print(f"{'='*80}")
    print(f"  Dataset     : {run['dataset_id']}")
    print(f"  Provider    : {run.get('provider', 'unknown')}")
    print(f"  Status      : {run['status']}")
    print(f"  Total Queries: {run['total_queries']}")
    print(f"  Started     : {run.get('started_at', 'n/a')}")
    print(f"  Finished    : {run.get('finished_at', 'n/a')}")

    # Overall metrics from aggregates.
    aggs = repository.get_aggregates(run_id, "overall")
    if aggs:
        print(f"\n  {'METRIC':<22} {'VALUE':>10}")
        print(f"  {'-'*32}")
        # V1 priority metrics first.
        priority = ["recall", "precision", "f1", "exact_match", "document_recall", "success_rate"]
        other = []
        shown = set()
        for name in priority:
            for a in aggs:
                if a["metric_name"] == name:
                    print(f"  {name:<22} {a['metric_value']:>10.4f}")
                    shown.add(name)
        for a in aggs:
            if a["metric_name"] not in shown and a["metric_name"] != "num_queries":
                print(f"  {a['metric_name']:<22} {a['metric_value']:>10.4f}")

    # Difficulty breakdown.
    diff_aggs = repository.get_aggregates(run_id, "difficulty")
    if diff_aggs:
        print(f"\n  BY DIFFICULTY:")
        by_diff = {}
        for a in diff_aggs:
            by_diff.setdefault(a["scope_value"], {})[a["metric_name"]] = a["metric_value"]
        for diff in sorted(by_diff):
            m = by_diff[diff]
            nq = int(m.get("num_queries", 0))
            print(f"    {diff:<10} (n={nq:>3})  F1={m.get('f1',0):.3f}  "
                  f"Recall={m.get('recall',0):.3f}  DocRecall={m.get('document_recall',0):.3f}  "
                  f"EM={m.get('exact_match',0):.3f}")

    # Failure taxonomy.
    fail_aggs = repository.get_aggregates(run_id, "failure_type")
    if fail_aggs:
        print(f"\n  FAILURE TAXONOMY:")
        for a in sorted(fail_aggs, key=lambda x: -x["metric_value"]):
            print(f"    {a['scope_value']:<30} {int(a['metric_value']):>5}")

    print()


def show_detail(run_id: str, max_rows: int = 20):
    metrics = repository.get_query_metrics(run_id)
    if not metrics:
        print(f"No per-query results for run {run_id}")
        return

    print(f"\n  PER-QUERY RESULTS (showing {min(len(metrics), max_rows)} of {len(metrics)}):")
    print(f"  {'QUERY_ID':<16} {'OK':<4} {'FAILURE':<24} {'Recall':>7} {'Prec':>7} "
          f"{'F1':>7} {'EM':>5} {'DocRec':>7}")
    print(f"  {'-'*90}")

    for m in metrics[:max_rows]:
        ok = "✓" if m.get("success") else "✗"
        print(f"  {m['query_id']:<16} {ok:<4} {m.get('failure_type',''):<24} "
              f"{m.get('recall',0):>7.3f} {m.get('precision',0):>7.3f} "
              f"{m.get('f1',0):>7.3f} {m.get('exact_match',0):>5.1f} "
              f"{m.get('document_recall',0):>7.3f}")

    if len(metrics) > max_rows:
        print(f"  ... ({len(metrics) - max_rows} more rows)")
    print()


def show_query(run_id: str, query_id: str):
    m = repository.get_query_metric(run_id, query_id)
    if not m:
        print(f"No result for query {query_id} in run {run_id}")
        return

    q = repository.get_query(query_id)
    resp = repository.get_response(run_id, query_id)

    print(f"\n{'='*80}")
    print(f"  QUERY INSPECTION: {query_id}")
    print(f"{'='*80}")

    if q:
        print(f"\n  Question    : {q.get('query_text', '')[:120]}")
        print(f"  GT Answer   : {q.get('gt_answer', '')[:120]}")
        print(f"  Difficulty  : {q.get('difficulty', '')}")
        print(f"  Eval Label  : {q.get('eval_label', '')}")
        cats = q.get("categories", [])
        if cats:
            print(f"  Categories  : {', '.join(cats)}")
        gt_facts = q.get("gt_supporting_facts", [])
        if gt_facts:
            print(f"  GT Facts ({len(gt_facts)}):")
            for f in gt_facts[:5]:
                print(f"    [{f.get('fact_id','')}] {f.get('text','')[:100]}")

    print(f"\n  Generated Answer: {m.get('generated_answer', '')[:200]}")

    print(f"\n  METRICS:")
    for k in ["recall", "precision", "f1", "exact_match", "document_recall"]:
        print(f"    {k:<22}: {m.get(k, 0):.4f}")
    print(f"    {'success':<22}: {m.get('success', False)}")
    print(f"    {'failure_type':<22}: {m.get('failure_type', '')}")

    if resp:
        payload = resp.get("raw_payload", {})
        ks = payload.get("knowledge_state", [])
        print(f"\n  RAW RESPONSE (path: {resp.get('raw_payload_path', 'n/a')}):")
        print(f"    Retrieval time   : {resp.get('retrieval_time_ms', 0)} ms")
        print(f"    Status           : {resp.get('status', '')}")
        print(f"    Nodes retrieved  : {len(ks)}")
        for i, node in enumerate(ks[:5]):
            facts = node.get("facts", [])
            print(f"    Node {i+1}: score={node.get('node_score',0):.3f}  "
                  f"doc={node.get('doc_id','')}  facts={len(facts)}")
            for f in facts[:3]:
                print(f"      - {f.get('text','')[:80]}")

    print()


def main():
    parser = argparse.ArgumentParser(description="View evaluation results.")
    parser.add_argument("run_id", nargs="?", default=None, help="Run ID to inspect.")
    parser.add_argument("--list", action="store_true", help="List all runs.")
    parser.add_argument("--detail", action="store_true", help="Show per-query detail.")
    parser.add_argument("--query", default=None, help="Inspect a specific query.")
    parser.add_argument("--all", action="store_true", help="Show all per-query rows.")
    args = parser.parse_args()

    if args.list or args.run_id is None:
        list_runs()
        if args.run_id is None and not args.list:
            print("Usage: python scripts/view_results.py [RUN_ID] [--detail] [--query QUERY_ID]")
        return

    show_run_summary(args.run_id)

    if args.query:
        show_query(args.run_id, args.query)
    elif args.detail:
        max_rows = 999 if args.all else 20
        show_detail(args.run_id, max_rows=max_rows)


if __name__ == "__main__":
    main()
