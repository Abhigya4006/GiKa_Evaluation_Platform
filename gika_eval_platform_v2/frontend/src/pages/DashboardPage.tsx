import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchRuns } from "../services/api";
import type { EvalRun } from "../types";
import StatusBadge from "../components/StatusBadge";

export default function DashboardPage() {
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    fetchRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading runs…</div>;
  if (error) return <div className="alert alert-error">{error}</div>;

  if (!runs.length) {
    return (
      <>
        <h1>Analytics</h1>
        <div className="empty-state">
          No evaluation runs found yet. Go to <strong>New Run</strong> to create one,
          or <strong>Datasets</strong> to upload a benchmark first.
        </div>
      </>
    );
  }

  return (
    <>
      <h1>Analytics</h1>
      <p className="subtitle">Select a run to view detailed analytics and results.</p>

      <table className="data-table">
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Dataset</th>
            <th>Provider</th>
            <th>Status</th>
            <th>Queries</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr
              key={r.run_id}
              className="clickable-row"
              onClick={() => navigate(`/analytics/${r.run_id}`)}
            >
              <td className="mono">{r.run_id}</td>
              <td>{r.dataset_id}</td>
              <td>{r.provider || "generic_http"}</td>
              <td><StatusBadge status={r.status} /></td>
              <td>{r.total_queries}</td>
              <td className="mono" style={{ fontSize: "0.78rem" }}>
                {r.started_at?.replace("T", " ").slice(0, 19) || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
