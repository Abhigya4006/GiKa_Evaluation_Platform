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

/**
 * Upload with real progress tracking via XMLHttpRequest.
 * onProgress receives a value between 0 and 100.
 */
export function uploadDatasetWithProgress(
  file: File,
  datasetId: string,
  name: string,
  version: string,
  onProgress: (pct: number) => void,
  csvMapping?: string,
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("dataset_id", datasetId);
    fd.append("name", name);
    fd.append("version", version);
    if (csvMapping) fd.append("csv_mapping", csvMapping);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/datasets/upload`);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        // Upload portion is 0-80%; remaining 20% is server processing.
        const pct = Math.round((e.loaded / e.total) * 80);
        onProgress(pct);
      }
    });

    xhr.upload.addEventListener("loadend", () => {
      // File fully sent; server is now parsing/validating.
      onProgress(85);
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100);
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResult);
        } catch {
          reject(new Error("Invalid JSON response"));
        }
      } else {
        let detail = xhr.responseText;
        try {
          const parsed = JSON.parse(xhr.responseText);
          detail = parsed.detail ?? xhr.responseText;
        } catch { /* not JSON */ }
        reject(new Error(`${xhr.status}: ${detail}`));
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Network error during upload")));
    xhr.addEventListener("abort", () => reject(new Error("Upload aborted")));

    xhr.send(fd);
  });
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
