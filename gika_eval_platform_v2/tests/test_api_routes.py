"""Tests for the new FastAPI REST API routes."""
from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


class TestHealth:
    def test_health(self):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


class TestDatasets:
    def test_list_datasets(self):
        res = client.get("/api/datasets")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        # The conftest seeds at least one dataset.
        assert len(data) >= 1
        assert "dataset_id" in data[0]
        assert "query_count" in data[0]

    def test_get_dataset(self):
        # We know "sample_benchmark" is seeded by conftest.
        res = client.get("/api/datasets")
        ds_id = res.json()[0]["dataset_id"]
        res2 = client.get(f"/api/datasets/{ds_id}")
        assert res2.status_code == 200
        assert res2.json()["dataset_id"] == ds_id

    def test_get_dataset_not_found(self):
        res = client.get("/api/datasets/nonexistent_dataset_12345")
        assert res.status_code == 404

    def test_get_dataset_queries(self):
        res = client.get("/api/datasets")
        ds_id = res.json()[0]["dataset_id"]
        res2 = client.get(f"/api/datasets/{ds_id}/queries")
        assert res2.status_code == 200
        queries = res2.json()
        assert isinstance(queries, list)
        assert len(queries) > 0

    def test_upload_json(self):
        """Upload a minimal JSON dataset."""
        dataset = {
            "dataset_id": "test_api_upload",
            "name": "API Test",
            "items": [
                {
                    "query_id": "q1",
                    "query": "What is the capital of France?",
                    "gt_answer": "Paris",
                    "gt_supporting_facts": [{"fact_id": "f1", "text": "Paris is the capital of France."}],
                    "gt_documents": [{"doc_id": "doc1"}],
                },
            ],
        }
        content = json.dumps(dataset).encode()
        res = client.post(
            "/api/datasets/upload",
            files={"file": ("test.json", io.BytesIO(content), "application/json")},
            data={"dataset_id": "test_api_upload", "name": "API Test", "version": "1.0.0"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["dataset_id"] == "test_api_upload"
        assert body["total_items"] == 1
        assert "capability_report" in body
        assert "validation_warnings" in body
        assert len(body["preview"]) == 1

    def test_ingest_after_upload(self):
        """Upload then ingest."""
        dataset = {
            "dataset_id": "test_ingest_flow",
            "name": "Ingest Flow Test",
            "items": [
                {
                    "query_id": "iq1",
                    "query": "Test query",
                    "gt_answer": "Test answer",
                    "gt_supporting_facts": [{"fact_id": "f1", "text": "fact"}],
                    "gt_documents": [{"doc_id": "d1"}],
                },
            ],
        }
        content = json.dumps(dataset).encode()
        client.post(
            "/api/datasets/upload",
            files={"file": ("test.json", io.BytesIO(content), "application/json")},
            data={"dataset_id": "test_ingest_flow", "name": "Ingest Test"},
        )
        res = client.post(
            "/api/datasets/ingest",
            data={"dataset_id": "test_ingest_flow"},
        )
        assert res.status_code == 200
        assert "test_ingest_flow" in res.json()["message"]


class TestMetrics:
    def test_list_metrics(self):
        res = client.get("/api/metrics")
        assert res.status_code == 200
        metrics = res.json()
        assert isinstance(metrics, list)
        assert len(metrics) >= 4
        names = [m["name"] for m in metrics]
        assert "recall" in names
        assert "f1" in names

    def test_metrics_by_category(self):
        res = client.get("/api/metrics/by-category/retrieval")
        assert res.status_code == 200
        metrics = res.json()
        assert all(m["category"] == "retrieval" for m in metrics)


class TestRuns:
    def test_list_runs(self):
        res = client.get("/api/runs")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_providers(self):
        res = client.get("/api/runs/providers")
        assert res.status_code == 200
        body = res.json()
        assert "providers" in body
        assert "mock_local" in body["providers"]

    def test_create_and_execute_run(self):
        """Create a run with mock_local and execute it."""
        # Use the sample benchmark dataset.
        ds_res = client.get("/api/datasets")
        ds_id = ds_res.json()[0]["dataset_id"]

        create_res = client.post("/api/runs", json={
            "dataset_id": ds_id,
            "provider": "mock_local",
            "local_mode": True,
            "run_name": "api-test-run",
        })
        assert create_res.status_code == 200
        run_id = create_res.json()["run_id"]
        assert create_res.json()["status"] == "pending"

        exec_res = client.post(f"/api/runs/{run_id}/execute")
        assert exec_res.status_code == 200
        body = exec_res.json()
        assert body["status"] in ("completed", "partial")
        assert body["run_id"] == run_id

    def test_get_run_detail(self):
        # Create and execute first.
        ds_res = client.get("/api/datasets")
        ds_id = ds_res.json()[0]["dataset_id"]
        create_res = client.post("/api/runs", json={
            "dataset_id": ds_id,
            "local_mode": True,
            "run_name": "detail-test",
        })
        run_id = create_res.json()["run_id"]
        client.post(f"/api/runs/{run_id}/execute")

        res = client.get(f"/api/runs/{run_id}")
        assert res.status_code == 200
        assert res.json()["run_id"] == run_id

    def test_dashboard_data(self):
        # Create and execute.
        ds_res = client.get("/api/datasets")
        ds_id = ds_res.json()[0]["dataset_id"]
        create_res = client.post("/api/runs", json={
            "dataset_id": ds_id,
            "local_mode": True,
        })
        run_id = create_res.json()["run_id"]
        client.post(f"/api/runs/{run_id}/execute")

        res = client.get(f"/api/runs/{run_id}/dashboard")
        assert res.status_code == 200
        body = res.json()
        assert "summary" in body
        assert "query_rows" in body
        assert "category" in body
        assert "difficulty" in body
        assert "documents" in body
        assert "leaderboard" in body


class TestCompare:
    def test_comparison_groups_empty_ok(self):
        res = client.get("/api/compare/groups")
        assert res.status_code == 200
        assert isinstance(res.json(), list)
