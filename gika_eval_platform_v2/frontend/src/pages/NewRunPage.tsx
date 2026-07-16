import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchDatasets,
  fetchProviders,
  fetchRuns,
  createRun,
  executeRun,
} from "../services/api";
import type { Dataset, EvalRun, ProvidersInfo } from "../types";
import MetricSelector from "../components/MetricSelector";
import StatusBadge from "../components/StatusBadge";

export default function NewRunPage() {
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [providers, setProviders] = useState<ProvidersInfo | null>(null);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state.
  const [datasetId, setDatasetId] = useState("");
  const [provider, setProvider] = useState("");
  const [localMode, setLocalMode] = useState(false);
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:8000/retrieve");
  const [runName, setRunName] = useState("");
  const [chatSubId, setChatSubId] = useState("gpt-5-mini");
  const [graphConfigs, setGraphConfigs] = useState(
    '[{"graph_id": "graph-1", "tenant_id": "kb_XXXX", "neo4j_database_name": "dbXXXX"}]'
  );
  const [extraJson, setExtraJson] = useState("");
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);

  // Progress.
  const [running, setRunning] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [error, setError] = useState("");
  const [finishedRunId, setFinishedRunId] = useState("");

  useEffect(() => {
    Promise.all([fetchDatasets(), fetchProviders(), fetchRuns()])
      .then(([ds, prov, rs]) => {
        setDatasets(ds);
        setProviders(prov);
        setRuns(rs);
        if (ds.length > 0) setDatasetId(ds[0].dataset_id);
        setProvider(prov.default);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleRun = async () => {
    setRunning(true);
    setError("");
    setStatusMsg("");
    setFinishedRunId("");

    try {
      const chosenProvider = localMode ? "mock_local" : provider;

      // Parse extra config.
      let extra: Record<string, unknown> = {};
      if (extraJson.trim()) {
        try {
          extra = JSON.parse(extraJson);
        } catch {
          throw new Error("Extra provider config is not valid JSON.");
        }
      }

      // Parse graph configs.
      let gc: unknown[] | undefined;
      if (graphConfigs.trim()) {
        try {
          gc = JSON.parse(graphConfigs);
        } catch {
          /* ignore */
        }
      }

      setStatusMsg("Creating run…");
      const { run_id } = await createRun({
        dataset_id: datasetId,
        provider: chosenProvider,
        api_endpoint: chosenProvider !== "mock_local" ? endpoint : "",
        run_name: runName || `dashboard-${chosenProvider}`,
        local_mode: localMode,
        selected_metrics: selectedMetrics.length > 0 ? selectedMetrics : undefined,
        chat_subscription_id: chatSubId,
        graph_configs: gc,
        extra_config: extra,
      });

      setStatusMsg(`Run ${run_id} created. Evaluating…`);
      const summary = await executeRun(run_id);
      const sr = (summary as Record<string, unknown>).overall as Record<string, unknown> | undefined;
      const successRate = sr?.success_rate;

      setFinishedRunId(run_id);
      setStatusMsg(
        `Run ${run_id} finished (${(summary as Record<string, unknown>).status}). ` +
        (successRate != null ? `Success rate: ${Number(successRate).toFixed(3)}` : "")
      );

      // Refresh runs list.
      fetchRuns().then(setRuns).catch(() => {});
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
        <h1>New Evaluation Run</h1>
        <div className="empty-state">
          No datasets ingested yet. Go to <strong>Datasets</strong> to upload one first.
        </div>
      </>
    );
  }

  return (
    <>
      <h1>New Evaluation Run</h1>
      <p className="subtitle">Select a dataset, configure metrics and provider, then launch.</p>

      {/* Dataset selector */}
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

      {/* Metric selector */}
      <MetricSelector
        selected={selectedMetrics}
        onChange={setSelectedMetrics}
      />

      {/* Provider config */}
      <div className="card">
        <div className="card-header">Configure Provider</div>
        <div className="row">
          <div>
            <div className="form-group">
              <label>Provider</label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                {providers?.providers.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <label className="checkbox-item">
              <input type="checkbox" checked={localMode} onChange={(e) => setLocalMode(e.target.checked)} />
              Use local mock retriever
            </label>
          </div>
          <div>
            <div className="form-group">
              <label>Endpoint URL</label>
              <input type="url" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Run Name (optional)</label>
              <input type="text" value={runName} onChange={(e) => setRunName(e.target.value)} />
            </div>
          </div>
        </div>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <div className="form-group">
            <label>chat_subscription_id</label>
            <input type="text" value={chatSubId} onChange={(e) => setChatSubId(e.target.value)} />
          </div>
          <div className="form-group">
            <label>graph_configs (JSON list)</label>
            <textarea value={graphConfigs} onChange={(e) => setGraphConfigs(e.target.value)} rows={3} />
          </div>
        </div>
        <div className="form-group" style={{ marginTop: "0.5rem" }}>
          <label>Extra provider config JSON (optional)</label>
          <textarea value={extraJson} onChange={(e) => setExtraJson(e.target.value)} rows={3}
            placeholder='{"key": "value"}' />
        </div>
      </div>

      {/* Run button */}
      <button className="btn btn-primary" onClick={handleRun} disabled={running}
        style={{ marginTop: "0.5rem" }}>
        {running ? "⏳ Running…" : "▶ Run Evaluation"}
      </button>

      {statusMsg && (
        <div className="alert alert-info" style={{ marginTop: "1rem" }}>{statusMsg}</div>
      )}
      {error && (
        <div className="alert alert-error" style={{ marginTop: "1rem" }}>{error}</div>
      )}
      {finishedRunId && (
        <button className="btn btn-primary" onClick={() => navigate(`/analytics/${finishedRunId}`)}
          style={{ marginTop: "0.5rem" }}>
          📊 Open in Analytics
        </button>
      )}

      {/* Run history */}
      <h2 style={{ marginTop: "2rem" }}>Recent Runs</h2>
      {runs.length === 0 ? (
        <div className="empty-state">No runs yet.</div>
      ) : (
        <div className="card" style={{ overflowX: "auto" }}>
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
              {runs.slice(0, 30).map((r) => (
                <tr key={r.run_id} className="clickable-row"
                  onClick={() => navigate(`/analytics/${r.run_id}`)}>
                  <td className="mono">{r.run_id}</td>
                  <td>{r.dataset_id}</td>
                  <td>{r.provider || "generic_http"}</td>
                  <td><StatusBadge status={r.status} /></td>
                  <td className="mono">{r.total_queries}</td>
                  <td className="mono" style={{ fontSize: "0.78rem" }}>
                    {r.started_at?.replace("T", " ").slice(0, 19) || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
