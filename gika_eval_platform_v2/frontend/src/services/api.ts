/**
 * Centralised API client.
 *
 * Every HTTP call goes through this module so the base URL, error handling,
 * and auth headers (if added later) are in one place.
 */
import type {
  CompareResult,
  DashboardData,
  Dataset,
  GTMergeResult,
  MetricDefinition,
  EvalRun,
  ProvidersInfo,
  QueryDetail,
  UploadResult,
} from "../types";

const BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      detail = parsed.detail ?? body;
    } catch { /* not JSON */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

/* ------------------------------------------------------------------ */
/* Datasets                                                            */
/* ------------------------------------------------------------------ */

export function fetchDatasets(): Promise<Dataset[]> {
  return request("/api/datasets");
}

export function fetchDataset(id: string): Promise<Dataset> {
  return request(`/api/datasets/${encodeURIComponent(id)}`);
}

export function uploadDataset(
  file: File,
  datasetId: string,
  name: string,
  version: string,
  csvMapping?: string,
): Promise<UploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("dataset_id", datasetId);
  fd.append("name", name);
  fd.append("version", version);
  if (csvMapping) fd.append("csv_mapping", csvMapping);
  return request("/api/datasets/upload", { method: "POST", body: fd });
}

export function mergeGroundTruth(
  file: File,
  datasetId: string,
): Promise<GTMergeResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("dataset_id", datasetId);
  return request("/api/datasets/gt-merge", { method: "POST", body: fd });
}

export function ingestDataset(datasetId: string): Promise<{ dataset_id: string; message: string }> {
  const fd = new FormData();
  fd.append("dataset_id", datasetId);
  return request("/api/datasets/ingest", { method: "POST", body: fd });
}

export function deleteDataset(id: string): Promise<{ message: string }> {
  return request(`/api/datasets/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/* ------------------------------------------------------------------ */
/* Metrics                                                             */
/* ------------------------------------------------------------------ */

export function fetchMetrics(): Promise<MetricDefinition[]> {
  return request("/api/metrics");
}

/* ------------------------------------------------------------------ */
/* Runs                                                                */
/* ------------------------------------------------------------------ */

export function fetchRuns(): Promise<EvalRun[]> {
  return request("/api/runs");
}

export function fetchProviders(): Promise<ProvidersInfo> {
  return request("/api/runs/providers");
}

export function createRun(body: Record<string, unknown>): Promise<{ run_id: string; status: string }> {
  return request("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function executeRun(runId: string): Promise<Record<string, unknown>> {
  return request(`/api/runs/${encodeURIComponent(runId)}/execute`, {
    method: "POST",
  });
}

export function fetchDashboard(runId: string): Promise<DashboardData> {
  return request(`/api/runs/${encodeURIComponent(runId)}/dashboard`);
}

export function fetchQueryDetail(
  runId: string,
  queryId: string,
): Promise<QueryDetail> {
  return request(
    `/api/runs/${encodeURIComponent(runId)}/queries/${encodeURIComponent(queryId)}`,
  );
}

export function compareRuns(
  runIdA: string,
  runIdB: string,
): Promise<{ aggregate: Record<string, unknown>[]; per_query: Record<string, unknown>[] }> {
  return request(
    `/api/runs/${encodeURIComponent(runIdA)}/compare/${encodeURIComponent(runIdB)}`,
  );
}

/* ------------------------------------------------------------------ */
/* Compare (side-by-side)                                              */
/* ------------------------------------------------------------------ */

export function runComparison(body: Record<string, unknown>): Promise<CompareResult> {
  return request("/api/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchComparisonGroups(): Promise<Record<string, unknown>[]> {
  return request("/api/compare/groups");
}

/* ------------------------------------------------------------------ */
/* Exports                                                             */
/* ------------------------------------------------------------------ */

export function exportRun(runId: string): Promise<{ run_id: string; files: Record<string, string> }> {
  return request(`/api/exports/${encodeURIComponent(runId)}`, { method: "POST" });
}

/* ------------------------------------------------------------------ */
/* Health                                                              */
/* ------------------------------------------------------------------ */

export function healthCheck(): Promise<{ status: string }> {
  return request("/api/health");
}
