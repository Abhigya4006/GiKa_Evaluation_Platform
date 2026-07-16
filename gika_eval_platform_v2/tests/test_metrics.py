
from app.metrics import (
    document_recall,
    exact_match,
    f1,
    precision,
    recall,
)
from app.metrics.metric_registry import compute_all_metrics, V1_ALL_METRICS
from app.evaluation.judge import HeuristicJudge


def _gt_facts():
    return [
        {"fact_id": "f1", "text": "The AI Act was published on 12 July 2024.", "doc_id": "docA"},
        {"fact_id": "f2", "text": "It entered into force on 1 August 2024.", "doc_id": "docA"},
    ]


def _gt_docs():
    return [{"doc_id": "docA", "filename": "act.pdf", "page_numbers": [1]}]


def _perfect_ks():
    return [{
        "rank": 1, "from_node_id": "n1", "node_score": 0.9,
        "doc_id": "docA", "filename": "act.pdf", "page_numbers": [1],
        "facts": [
            {"fact_id": "f1", "text": "The AI Act was published on 12 July 2024."},
            {"fact_id": "f2", "text": "It entered into force on 1 August 2024."},
        ],
    }]


def test_recall_full_and_partial():
    assert recall.recall(_gt_facts(), _perfect_ks()) == 1.0
    partial = [{"rank": 1, "from_node_id": "n", "doc_id": "docA", "filename": "act.pdf",
                "facts": [{"fact_id": "f1", "text": "x"}]}]
    assert recall.recall(_gt_facts(), partial) == 0.5


def test_precision_counts_relevant():
    ks = [{"rank": 1, "from_node_id": "n", "doc_id": "docA", "filename": "act.pdf",
           "facts": [
               {"fact_id": "f1", "text": "The AI Act was published on 12 July 2024."},
               {"fact_id": None, "text": "unrelated noise"},
           ]}]
    assert precision.precision(_gt_facts(), ks) == 0.5


def test_f1_harmonic():
    assert f1.f1(0.5, 0.5) == 0.5
    assert f1.f1(0.0, 1.0) == 0.0


def test_document_recall():
    assert document_recall.document_recall(_gt_docs(), _perfect_ks()) == 1.0
    wrong = [{"rank": 1, "from_node_id": "n", "doc_id": "docZ", "filename": "other.pdf", "facts": []}]
    assert document_recall.document_recall(_gt_docs(), wrong) == 0.0


def test_exact_match_multi_answer():
    ks = []
    generated = "The mother is Tracy McConnell."
    # Passing the whole list should match the second entry.
    assert exact_match.exact_match_any(
        ["The Mother", "Tracy McConnell"], ks, generated_answer=generated
    ) == 1.0
    # No overlap -> 0.
    assert exact_match.exact_match_any(
        ["Somebody Else"], ks, generated_answer=generated
    ) == 0.0


def test_v1_registry_bundle_is_v1_only():
    query = {
        "gt_answer": "12 July 2024",
        "gt_answers": ["12 July 2024"],
        "gt_supporting_facts": _gt_facts(),
        "gt_documents": _gt_docs(),
    }
    resp = {"knowledge_state": _perfect_ks()}
    judge_result = HeuristicJudge().evaluate(
        question="When was it published?",
        generated_answer="On 12 July 2024.",
        gt_answers=["12 July 2024"],
    )
    m = compute_all_metrics(query, resp, generated_answer="On 12 July 2024.", judge_result=judge_result)

    # All V1 metrics present.
    for k in V1_ALL_METRICS:
        assert k in m, f"missing V1 metric {k}"

    # Ranking metrics MUST NOT be present in the V1 bundle.
    for banned in ("mrr", "ndcg", "map_score",
                   "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10",
                   "answerability_score"):
        assert banned not in m, f"deferred metric {banned} leaked into V1 registry output"

    # Judge output plumbed through.
    assert m["llm_judge_score"] is not None
    assert m["llm_judge_verdict"] in ("correct", "partial", "incorrect")

    # metric_details present for the failure taxonomy.
    assert "metric_details" in m
    assert m["metric_details"]["num_gt_facts"] == 2


def test_heuristic_judge_multi_answer():
    j = HeuristicJudge()
    r = j.evaluate(
        question="Who ends up with the narrator?",
        generated_answer="Tracy McConnell.",
        gt_answers=["Tracy McConnell", "The Mother (How I Met Your Mother)"],
    )
    assert r["score"] == 1.0
    assert r["verdict"] == "correct"

    r2 = j.evaluate(
        question="Where was he born?",
        generated_answer="I don't know.",
        gt_answers=["Ocala"],
    )
    assert r2["verdict"] in ("partial", "incorrect")
