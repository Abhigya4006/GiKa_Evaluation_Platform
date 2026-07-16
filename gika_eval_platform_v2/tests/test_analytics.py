
from pathlib import Path

from app.api_client.mock_api import build_response
from app.core.enums import ScopeType
from app.db import repository
from app.evaluation.runner import run_evaluation
from app.insights.generators import generate_insights
from app.services.export_service import export_run
from app.services.leaderboard_service import leaderboard_comparison
from app.services.run_service import create_run


def _completed_run():
    run_id = create_run("eu_ai_act_bench", run_name="pytest-analytics")
    run_evaluation(run_id, local_fn=build_response)
    return run_id


def test_aggregates_written():
    run_id = _completed_run()
    overall = repository.get_aggregates(run_id, ScopeType.OVERALL.value)
    names = {a["metric_name"] for a in overall}
    assert "recall" in names and "success_rate" in names and "num_queries" in names
    assert repository.get_aggregates(run_id, ScopeType.CATEGORY.value)
    assert repository.get_aggregates(run_id, ScopeType.DIFFICULTY.value)


def test_insights_structure():
    run_id = _completed_run()
    ins = generate_insights(run_id, "eu_ai_act_bench")
    assert ins["num_queries"] == 32
    assert "weakest_categories" in ins
    assert "failure_counts" in ins
    assert isinstance(ins["hard_failure_queries"], list)


def test_leaderboard_comparison():
    run_id = _completed_run()
    rows = leaderboard_comparison(run_id, "eu_ai_act_bench")
    assert rows
    for r in rows:
        assert "gap" in r and "current_run" in r


def test_export_writes_files():
    run_id = _completed_run()
    paths = export_run(run_id)
    for key in ("per_query_csv", "query_metrics_csv", "aggregates_csv",
                "failure_taxonomy_csv", "insights_json", "insights_report"):
        assert key in paths
        assert Path(paths[key]).exists()
