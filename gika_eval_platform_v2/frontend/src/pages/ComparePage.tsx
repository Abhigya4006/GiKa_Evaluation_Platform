import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import {
  fetchDatasets,
  fetchProviders,
  runComparison,
  fetchComparisonGroups,
} from "../services/api";
import type { Dataset, ProvidersInfo, CompareResult, CompareRow } from "../types";
import MetricSelector from "../components/MetricSelector";

export default function ComparePage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [providers, setProviders] = useState<ProvidersInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const [datasetId, setDatasetId] = useState("");
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);

  // System A.
  const [aName, setAName] = useState("System A");
  const [aProvider, setAProvider] = useState("mock_local");
  const [aLocal, setALocal] = useState(true);
  const [aEndpoint, setAEndpoint] = useState("http://127.0.0.1:8000/retrieve");

  // System B.
  const [bName, setBName] = useState("System B");
  const [bProvider, setBProvider] = useState("mock_local");
  const [bLocal, setBLocal] = useState(true);
  const [bEndpoint, setBEndpoint] = useState("http://127.0.0.1:8001/retrieve");

  // Results.
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState("");

  // Historical groups.
  const [groups, setGroups] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    Promise.all([fetchDatasets(), fetchProviders(), fetchComparisonGroups()])
      .then(([ds, prov, grps]) => {
        setDatasets(ds);
        setProviders(prov);
        setGroups(grps);
        if (ds.length > 0) setDatasetId(ds[0].dataset_id);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleCompare = async () => {
    setRunning(true);
    setError("");
    setResult(null);

    try {
      const res = await runComparison({
        dataset_id: datasetId,
        system_a: { name: aName, provider: aLocal ? "mock_local" : aProvider, local_mode: aLocal, endpoint: aEndpoint },
        system_b: { name: bName, provider: bLocal ? "mock_local" : bProvider, local_mode: bLocal, endpoint: bEndpoint },
        selected_metrics: selectedMetrics.length > 0 ? selectedMetrics : undefined,
      });
      setResult(res);
      // Refresh groups.
      fetchComparisonGroups().then(setGroups).catch(() => {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <div className="loading">Loading…</div>;

  if (!datasets.length) {
    return (
      <>
        <h1>Side-by-Side Comparison</h1>
        <div className="empty-state">No datasets ingested yet. Go to <strong>Datasets</strong> first.</div>
      </>
    );
  }

  const providerList = providers?.providers ?? [];

  // Chart data from aggregate comparison.
  const chartMetrics = ["recall", "precision", "f1", "document_recall", "exact_match", "semantic_similarity", "success_rate"];
  const chartData = result?.aggregate
    ?.filter((r: CompareRow) => chartMetrics.includes(r.metric))
    .map((r: CompareRow) => ({
      metric: r.metric,
      [result.system_a.name]: r.run_a ?? 0,
      [result.system_b.name]: r.run_b ?? 0,
    })) ?? [];

  return (
    <>
      <h1>Side-by-Side Comparison</h1>
      <p className="subtitle">
        Configure two retrieval systems and benchmark them on the same dataset.
      </p>

      {/* Dataset */}
      <div className="form-group">
        <label>Dataset</label>
        <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
          {datasets.map((d) => (
            <option key={d.dataset_id} value={d.dataset_id}>
              {d.dataset_id} ({d.query_count} queries)
            </option>
          ))}
        </select>
      </div>

      <MetricSelector selected={selectedMetrics} onChange={setSelectedMetrics} />

      {/* Two systems side by side */}
      <div className="row">
        {/* System A */}
        <div className="card">
          <div className="card-header">System A</div>
          <div className="form-group">
            <label>Display Name</label>
            <input type="text" value={aName} onChange={(e) => setAName(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Provider</label>
            <select value={aProvider} onChange={(e) => setAProvider(e.target.value)}>
              {providerList.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <label className="checkbox-item" style={{ marginBottom: "0.75rem" }}>
            <input type="checkbox" checked={aLocal} onChange={(e) => setALocal(e.target.checked)} />
            Use local mock
          </label>
          <div className="form-group">
            <label>Endpoint URL</label>
            <input type="url" value={aEndpoint} onChange={(e) => setAEndpoint(e.target.value)} />
          </div>
        </div>

        {/* System B */}
        <div className="card">
          <div className="card-header">System B</div>
          <div className="form-group">
            <label>Display Name</label>
            <input type="text" value={bName} onChange={(e) => setBName(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Provider</label>
            <select value={bProvider} onChange={(e) => setBProvider(e.target.value)}>
              {providerList.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <label className="checkbox-item" style={{ marginBottom: "0.75rem" }}>
            <input type="checkbox" checked={bLocal} onChange={(e) => setBLocal(e.target.checked)} />
            Use local mock
          </label>
          <div className="form-group">
            <label>Endpoint URL</label>
            <input type="url" value={bEndpoint} onChange={(e) => setBEndpoint(e.target.value)} />
          </div>
        </div>
      </div>

      <button className="btn btn-primary" onClick={handleCompare} disabled={running}
        style={{ marginTop: "0.5rem" }}>
        {running ? "⏳ Running comparison…" : "▶ Run Comparison"}
      </button>

      {error && <div className="alert alert-error" style={{ marginTop: "1rem" }}>{error}</div>}

      {/* Comparison results */}
      {result && (
        <>
          <div className="alert alert-success" style={{ marginTop: "1rem" }}>
            Comparison group: <strong>{result.group_id}</strong> —
            {result.system_a.name} vs {result.system_b.name} completed.
          </div>

          <h2>Aggregate Comparison</h2>
          <div className="card" style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>{result.system_a.name}</th>
                  <th>{result.system_b.name}</th>
                  <th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {result.aggregate.map((r: CompareRow, i: number) => (
                  <tr key={i}>
                    <td>{r.metric}</td>
                    <td className="mono">{r.run_a?.toFixed(4) ?? "—"}</td>
                    <td className="mono">{r.run_b?.toFixed(4) ?? "—"}</td>
                    <td className="mono" style={{
                      color: r.delta != null
                        ? (r.delta >= 0 ? "var(--color-success)" : "var(--color-error)")
                        : undefined,
                    }}>
                      {r.delta != null ? (r.delta >= 0 ? "+" : "") + r.delta.toFixed(4) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {chartData.length > 0 && (
            <div className="card" style={{ minHeight: 260, marginTop: "1rem" }}>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="metric" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} />
                  <YAxis domain={[0, 1]} tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }} />
                  <Legend />
                  <Bar dataKey={result.system_a.name} fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey={result.system_b.name} fill="var(--color-success)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {result.per_query.length > 0 && (
            <>
              <h2>Per-Query Differences</h2>
              <div className="card" style={{ overflowX: "auto", maxHeight: 400, overflowY: "auto" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Query ID</th>
                      <th>F1 (A)</th>
                      <th>F1 (B)</th>
                      <th>F1 Δ</th>
                      <th>Recall (A)</th>
                      <th>Recall (B)</th>
                      <th>Recall Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.per_query.slice(0, 100).map((r, i) => (
                      <tr key={i}>
                        <td className="mono">{String(r.query_id)}</td>
                        <td className="mono">{r.f1_a != null ? Number(r.f1_a).toFixed(3) : "—"}</td>
                        <td className="mono">{r.f1_b != null ? Number(r.f1_b).toFixed(3) : "—"}</td>
                        <td className="mono">{r.f1_delta != null ? Number(r.f1_delta).toFixed(4) : "—"}</td>
                        <td className="mono">{r.recall_a != null ? Number(r.recall_a).toFixed(3) : "—"}</td>
                        <td className="mono">{r.recall_b != null ? Number(r.recall_b).toFixed(3) : "—"}</td>
                        <td className="mono">{r.recall_delta != null ? Number(r.recall_delta).toFixed(4) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}

      {/* Historical comparison groups */}
      <h2>Historical Comparison Groups</h2>
      {groups.length === 0 ? (
        <div className="empty-state">No comparison groups yet. Run a comparison above to create one.</div>
      ) : (
        groups.map((g: Record<string, unknown>) => (
          <div className="card" key={String(g.group_id)} style={{ marginBottom: "0.75rem" }}>
            <div className="card-header">
              Group: {String(g.group_id)} ({(g.runs as unknown[])?.length ?? 0} runs)
            </div>
            <table className="data-table">
              <thead>
                <tr><th>Run ID</th><th>Name</th><th>Provider</th><th>Status</th><th>F1</th><th>Recall</th><th>Success Rate</th></tr>
              </thead>
              <tbody>
                {((g.runs ?? []) as Record<string, unknown>[]).map((r) => (
                  <tr key={String(r.run_id)}>
                    <td className="mono">{String(r.run_id)}</td>
                    <td>{String(r.run_name || "")}</td>
                    <td>{String(r.provider || "")}</td>
                    <td>{String(r.status || "")}</td>
                    <td className="mono">{r.f1 != null ? Number(r.f1).toFixed(3) : "—"}</td>
                    <td className="mono">{r.recall != null ? Number(r.recall).toFixed(3) : "—"}</td>
                    <td className="mono">{r.success_rate != null ? Number(r.success_rate).toFixed(3) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </>
  );
}
