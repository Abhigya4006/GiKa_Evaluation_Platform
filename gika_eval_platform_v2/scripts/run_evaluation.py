
from __future__ import annotations

import os as _os, sys as _sys  # noqa: E402
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import json

from app.core.logging import get_logger
from app.db.init_db import init_db
from app.services.run_service import create_run, ingest_dataset
from app.services.export_service import export_run
from app.evaluation.runner import run_evaluation
from app.api_client.providers import available_providers

logger = get_logger("run_evaluation")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an evaluation over an ingested benchmark.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Registered providers: {', '.join(available_providers())}",
    )
    parser.add_argument("--dataset-id", default="musique_validation",
                        help="Dataset id (must already be ingested).")
    parser.add_argument("--provider", default=None,
                        help=f"Provider name. One of: {', '.join(available_providers())}. "
                             f"Defaults to generic_http (or mock_local with --local).")
    parser.add_argument("--endpoint", default=None,
                        help="Retrieval endpoint URL (used by HTTP providers).")
    parser.add_argument("--provider-config", default=None,
                        help="Optional JSON string with extra provider config "
                             "(auth, headers, extra.graph_configs, "
                             "extra.chat_subscription_id, timeout_s).")
    parser.add_argument("--run-name", default="cli-run")
    parser.add_argument("--local", action="store_true",
                        help="Shortcut for --provider mock_local (in-process, no HTTP).")
    parser.add_argument("--export", action="store_true", help="Export outputs after the run.")
    parser.add_argument("--init", action="store_true", help="Init DB + ingest before running.")
    parser.add_argument("--resume", default=None, help="Resume an existing run_id.")
    parser.add_argument("--dataset-json", default=None,
                        help="Optional path to a dataset JSON to ingest before the run "
                             "(routed through the adapter registry).")
    args = parser.parse_args()

    if args.init:
        init_db()
        ingest_dataset(args.dataset_json)
    elif args.dataset_json:
        ingest_dataset(args.dataset_json)

    from app.db import repository
    if repository.get_dataset(args.dataset_id) is None:
        logger.info("Dataset %s not found; ingesting sample dataset.", args.dataset_id)
        ingest_dataset()

    # Resolve provider name.
    provider = args.provider
    if args.local:
        provider = "mock_local"
    elif provider is None and args.endpoint:
        provider = "generic_http"
    elif provider is None:
        provider = "mock_local"

    # Parse provider_config.
    provider_config = {}
    if args.provider_config:
        try:
            provider_config = json.loads(args.provider_config)
        except json.JSONDecodeError as exc:
            parser.error(f"--provider-config must be valid JSON: {exc}")
    if args.endpoint:
        provider_config["endpoint"] = args.endpoint

    run_id = args.resume or create_run(
        args.dataset_id,
        api_endpoint=args.endpoint,
        run_name=args.run_name,
        provider=provider,
        provider_config=provider_config or None,
    )
    summary = run_evaluation(run_id)

    print("\n=== RUN SUMMARY (V1) ===")
    print(f"run_id           : {summary['run_id']}")
    print(f"provider         : {summary.get('provider')}")
    print(f"answer_generator : {summary.get('answer_generator')}")
    print(f"judge            : {summary.get('judge')}")
    print(f"status           : {summary['status']}")
    print(f"queries          : {summary['total_queries']}")
    ov = summary["overall"]
    # V1 metric print order (Directive Section 5.1). Ranking metrics
    # (MRR/NDCG/MAP) intentionally omitted per Section 5.2.
    for k in ("recall", "precision", "f1", "document_recall",
              "exact_match", "semantic_similarity", "llm_judge_score",
              "success_rate"):
        if k in ov and ov[k] is not None:
            print(f"  {k:20s}: {ov[k]:.4f}")

    if args.export:
        paths = export_run(run_id)
        print("\n=== EXPORTS ===")
        for k, v in paths.items():
            print(f"  {k}: {v}")

    print(f"\nRUN_ID={summary['run_id']}")


if __name__ == "__main__":
    main()
