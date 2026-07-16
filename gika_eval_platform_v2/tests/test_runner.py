
from app.api_client.mock_api import build_response
from app.api_client.providers import available_providers, get_provider
from app.api_client.base import ProviderConfig
from app.db import repository
from app.evaluation import checkpoint
from app.evaluation.runner import run_evaluation
from app.services.run_service import create_run


def test_run_completes_and_persists_v1_fields():
    run_id = create_run("eu_ai_act_bench", run_name="pytest-run")
    summary = run_evaluation(run_id, local_fn=build_response)
    assert summary["status"] in ("completed", "partial")
    assert summary["total_queries"] == 32

    # V1 summary must expose the answer generator + judge names.
    assert summary["answer_generator"] in ("extractive", "llm")
    assert summary["judge"] in ("heuristic", "llm")

    metrics = repository.get_query_metrics(run_id)
    assert len(metrics) == 32
    # V1 columns should be populated.
    m0 = metrics[0]
    for k in ("recall", "precision", "f1", "document_recall",
              "exact_match", "generated_answer", "success", "failure_type"):
        assert k in m0
    # Judge fields plumbed through.
    assert "llm_judge_score" in m0
    assert "llm_judge_verdict" in m0

    responses = repository.stored_query_ids(run_id)
    assert len(responses) == 32


def test_run_on_musique_slice_end_to_end():
    run_id = create_run("musique_test_slice", run_name="pytest-musique",
                        provider="mock_local")
    summary = run_evaluation(run_id, local_fn=build_response)
    assert summary["status"] in ("completed", "partial")
    assert summary["total_queries"] == 5

    metrics = repository.get_query_metrics(run_id)
    assert len(metrics) == 5
    # Every query should have a generated answer since mock retrieval returned
    # something for each.
    for m in metrics:
        assert m.get("generated_answer") is not None
        # V1 answer-side metrics computed against the multi-answer list.
        assert m.get("exact_match") is not None


def test_resume_is_idempotent():
    run_id = create_run("eu_ai_act_bench", run_name="pytest-resume")
    run_evaluation(run_id, local_fn=build_response)
    n1 = len(repository.get_query_metrics(run_id))
    run_evaluation(run_id, local_fn=build_response)
    n2 = len(repository.get_query_metrics(run_id))
    assert n1 == n2 == 32
    assert len(checkpoint.load_completed(run_id)) == 32


def test_failure_taxonomy_has_spread():
    run_id = create_run("eu_ai_act_bench", run_name="pytest-spread")
    run_evaluation(run_id, local_fn=build_response)
    metrics = repository.get_query_metrics(run_id)
    labels = {m["failure_type"] for m in metrics}
    assert "success" in labels
    assert len(labels) >= 2


def test_provider_registry_v1_signature():
    import inspect
    for name in available_providers():
        p = get_provider(name, ProviderConfig(endpoint="http://x/y"))
        assert p.name == name
        for method_name in ("build_request", "call", "normalize", "retrieve"):
            assert hasattr(p, method_name), f"{name} missing {method_name}"
        # build_request signature is (query_text, query_id, dataset_id).
        sig = inspect.signature(p.build_request)
        params = list(sig.parameters.keys())
        assert "top_k" not in params, (
            f"{name}.build_request still has a top_k param — V1 forbids this."
        )


def test_gika_provider_builds_v1_request_payload():
    from app.api_client.providers.gika_retrieve import GikaRetrieveProvider
    graph_configs = [{
        "graph_id": "graph-1",
        "tenant_id": "kb_test",
        "neo4j_database_name": "dbtest",
    }]
    p = GikaRetrieveProvider(ProviderConfig(
        endpoint="http://gika/retrieve",
        extra={"graph_configs": graph_configs, "chat_subscription_id": "gpt-5-mini"},
    ))
    payload = p.build_request("q?", "q_0001", dataset_id=None)
    assert payload == {
        "query": "q?",
        "query_id": "q_0001",
        "graph_configs": graph_configs,
        "chat_subscription_id": "gpt-5-mini",
    }
    # No top_k, no dataset_id on the wire.
    assert "top_k" not in payload
    assert "dataset_id" not in payload


def test_explicit_mock_local_provider():
    run_id = create_run("eu_ai_act_bench", run_name="pytest-explicit-mock",
                        provider="mock_local")
    summary = run_evaluation(run_id)
    assert summary["status"] in ("completed", "partial")
    assert summary["provider"] == "mock_local"
    assert summary["total_queries"] == 32


def test_run_row_persists_provider():
    run_id = create_run("eu_ai_act_bench", run_name="pytest-persisted-provider",
                        provider="gika_retrieve",
                        api_endpoint="http://example/retrieve")
    run = repository.get_run(run_id)
    assert run["provider"] == "gika_retrieve"
    assert run["api_endpoint"] == "http://example/retrieve"
