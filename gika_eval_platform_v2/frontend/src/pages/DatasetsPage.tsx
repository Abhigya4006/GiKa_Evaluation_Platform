import { useEffect, useState, useRef } from "react";
import {
  fetchDatasets,
  uploadDataset,
  ingestDataset,
  mergeGroundTruth,
  deleteDataset,
} from "../services/api";
import type { Dataset, UploadResult, GTMergeResult, CapabilityReport } from "../types";
import StatusBadge from "../components/StatusBadge";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Upload state.
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dsId, setDsId] = useState("");
  const [dsName, setDsName] = useState("");
  const [dsVersion, setDsVersion] = useState("1.0.0");

  // GT merge.
  const gtRef = useRef<HTMLInputElement>(null);
  const [gtResult, setGtResult] = useState<GTMergeResult | null>(null);
  const [gtError, setGtError] = useState("");

  // Ingest.
  const [ingestMsg, setIngestMsg] = useState("");
  const [ingestError, setIngestError] = useState("");

  const reload = () => {
    fetchDatasets()
      .then(setDatasets)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(reload, []);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError("");
    setUploadResult(null);
    setGtResult(null);
    setIngestMsg("");
    setIngestError("");

    try {
      const result = await uploadDataset(file, dsId, dsName, dsVersion);
      setUploadResult(result);
      setDsId(result.dataset_id);
      setDsName(result.name);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  const handleGtMerge = async () => {
    const file = gtRef.current?.files?.[0];
    if (!file || !uploadResult) return;
    setGtError("");
    try {
      const result = await mergeGroundTruth(file, uploadResult.dataset_id);
      setGtResult(result);
      // Update the capability report in uploadResult.
      setUploadResult({
        ...uploadResult,
        capability_report: result.updated_capability_report,
      });
    } catch (e: unknown) {
      setGtError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleIngest = async () => {
    if (!uploadResult) return;
    setIngestError("");
    setIngestMsg("");
    try {
      const result = await ingestDataset(uploadResult.dataset_id);
      setIngestMsg(result.message);
      setUploadResult(null);
      reload();
    } catch (e: unknown) {
      setIngestError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`Delete dataset "${id}"?`)) return;
    try {
      await deleteDataset(id);
      reload();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    }
  };

  const renderCapabilityReport = (report: CapabilityReport) => (
    <div className="card" style={{ marginTop: "0.75rem" }}>
      <div className="card-header">
        Dataset Capability Analysis — <StatusBadge status={report.status} />
      </div>
      <div className="row">
        <div>
          <strong style={{ fontSize: "0.82rem" }}>Detected fields:</strong>
          {report.detected_fields.map((f) => (
            <div key={f} style={{ fontSize: "0.82rem", color: "var(--color-success)" }}>✓ {f}</div>
          ))}
          {report.missing_fields.length > 0 && (
            <>
              <strong style={{ fontSize: "0.82rem", marginTop: "0.5rem", display: "block" }}>Missing fields:</strong>
              {report.missing_fields.map((f) => (
                <div key={f} style={{ fontSize: "0.82rem", color: "var(--color-error)" }}>✗ {f}</div>
              ))}
            </>
          )}
        </div>
        <div>
          <strong style={{ fontSize: "0.82rem" }}>Supported metrics:</strong>
          {report.supported_metrics.map((m) => (
            <div key={m} style={{ fontSize: "0.82rem", color: "var(--color-success)" }}>✓ {m}</div>
          ))}
          {report.unsupported_metrics.length > 0 && (
            <>
              <strong style={{ fontSize: "0.82rem", marginTop: "0.5rem", display: "block" }}>Unavailable metrics:</strong>
              {report.unsupported_metrics.map((m) => (
                <div key={m} style={{ fontSize: "0.82rem", color: "var(--color-warning)" }}>✗ {m}</div>
              ))}
            </>
          )}
        </div>
      </div>
      {report.warnings.length > 0 && (
        <div style={{ marginTop: "0.75rem" }}>
          {report.warnings.map((w, i) => (
            <div key={i} className="alert alert-warning" style={{ marginBottom: "0.3rem" }}>{w}</div>
          ))}
        </div>
      )}
      {report.errors.length > 0 && (
        <div style={{ marginTop: "0.5rem" }}>
          {report.errors.map((e, i) => (
            <div key={i} className="alert alert-error" style={{ marginBottom: "0.3rem" }}>{e}</div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <>
      <h1>Datasets</h1>
      <p className="subtitle">Upload, validate, and ingest benchmark datasets.</p>

      {/* Ingested datasets */}
      {loading ? (
        <div className="loading">Loading…</div>
      ) : error ? (
        <div className="alert alert-error">{error}</div>
      ) : datasets.length > 0 ? (
        <div className="card">
          <div className="card-header">Ingested Datasets ({datasets.length})</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Dataset ID</th>
                <th>Name</th>
                <th>Version</th>
                <th>Domain</th>
                <th>Queries</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.dataset_id}>
                  <td className="mono">{d.dataset_id}</td>
                  <td>{d.name}</td>
                  <td>{d.version}</td>
                  <td>{d.domain}</td>
                  <td className="mono">{d.query_count}</td>
                  <td className="mono" style={{ fontSize: "0.78rem" }}>
                    {d.created_at?.replace("T", " ").slice(0, 19) || "—"}
                  </td>
                  <td>
                    <button className="btn btn-secondary btn-sm" onClick={() => handleDelete(d.dataset_id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state" style={{ marginBottom: "1.5rem" }}>
          No datasets ingested yet. Upload one below.
        </div>
      )}

      {/* Upload form */}
      <h2>Upload</h2>
      <div className="card">
        <div className="row">
          <div className="form-group">
            <label>Benchmark file (JSON or CSV)</label>
            <input type="file" ref={fileRef} accept=".json,.csv,.tsv"
              style={{ fontSize: "0.85rem" }} />
          </div>
          <div className="form-group">
            <label>Dataset ID</label>
            <input type="text" value={dsId} onChange={(e) => setDsId(e.target.value)}
              placeholder="auto-generated from filename" />
          </div>
          <div className="form-group">
            <label>Display Name</label>
            <input type="text" value={dsName} onChange={(e) => setDsName(e.target.value)}
              placeholder="optional" />
          </div>
          <div className="form-group">
            <label>Version</label>
            <input type="text" value={dsVersion} onChange={(e) => setDsVersion(e.target.value)} />
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>
          {uploading ? "Uploading…" : "Upload & Parse"}
        </button>
      </div>

      {uploadError && <div className="alert alert-error">{uploadError}</div>}

      {/* Upload result */}
      {uploadResult && (
        <>
          <div className="alert alert-success">
            Parsed <strong>{uploadResult.dataset_id}</strong> ({uploadResult.format}) —
            {uploadResult.total_items} queries
          </div>

          {/* Preview */}
          <div className="card" style={{ overflowX: "auto" }}>
            <div className="card-header">Preview (first {uploadResult.preview.length})</div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Query ID</th>
                  <th>Query</th>
                  <th>GT Answer</th>
                  <th>Difficulty</th>
                  <th>Categories</th>
                  <th>#Facts</th>
                  <th>#Docs</th>
                </tr>
              </thead>
              <tbody>
                {uploadResult.preview.map((r) => (
                  <tr key={r.query_id}>
                    <td className="mono">{r.query_id}</td>
                    <td>{r.query}</td>
                    <td>{r.gt_answer}</td>
                    <td><span className="tag">{r.difficulty}</span></td>
                    <td>{r.categories?.join(", ")}</td>
                    <td className="mono">{r.facts_count}</td>
                    <td className="mono">{r.docs_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Capability report */}
          {renderCapabilityReport(uploadResult.capability_report)}

          {/* Validation warnings */}
          {uploadResult.validation_warnings.length > 0 && (
            <div className="card" style={{ marginTop: "0.75rem" }}>
              <div className="card-header">Validation Warnings ({uploadResult.validation_warnings.length})</div>
              {uploadResult.validation_warnings.map((w, i) => (
                <div key={i} style={{ fontSize: "0.82rem", color: "var(--color-warning)", marginBottom: "0.2rem" }}>
                  ⚠️ {w}
                </div>
              ))}
            </div>
          )}
          {uploadResult.validation_warnings.length === 0 && (
            <div className="alert alert-success" style={{ marginTop: "0.5rem" }}>
              ✅ Validation passed — no schema warnings.
            </div>
          )}

          {/* GT merge */}
          <div className="card" style={{ marginTop: "1rem" }}>
            <div className="card-header">Upload Separate Ground Truth (Optional)</div>
            <p style={{ fontSize: "0.82rem", color: "var(--color-text-muted)", marginBottom: "0.75rem" }}>
              Upload a JSON file with ground-truth records matched by query_id.
            </p>
            <input type="file" ref={gtRef} accept=".json" style={{ fontSize: "0.85rem" }} />
            <button className="btn btn-secondary" onClick={handleGtMerge}
              style={{ marginLeft: "0.75rem", marginTop: "0.5rem" }}>
              Merge Ground Truth
            </button>
            {gtError && <div className="alert alert-error" style={{ marginTop: "0.5rem" }}>{gtError}</div>}
            {gtResult && (
              <div className="alert alert-success" style={{ marginTop: "0.5rem" }}>
                Merged {gtResult.matched_count} records.
                {gtResult.unmatched_gt_ids.length > 0 && (
                  <> ({gtResult.unmatched_gt_ids.length} GT IDs had no match.)</>
                )}
              </div>
            )}
          </div>

          {/* Ingest */}
          <div style={{ marginTop: "1rem" }}>
            <button className="btn btn-primary" onClick={handleIngest}>
              💾 Ingest Dataset
            </button>
            {ingestMsg && <div className="alert alert-success" style={{ marginTop: "0.5rem" }}>{ingestMsg}</div>}
            {ingestError && <div className="alert alert-error" style={{ marginTop: "0.5rem" }}>{ingestError}</div>}
          </div>
        </>
      )}
    </>
  );
}
