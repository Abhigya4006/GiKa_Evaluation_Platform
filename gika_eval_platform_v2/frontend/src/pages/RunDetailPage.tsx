import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { fetchDashboard, fetchQueryDetail, fetchRuns, compareRuns } from "../services/api";
import type { DashboardData, EvalRun, QueryDetail, QueryRow } from "../types";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters for query table.
  const [diffFilter, setDiffFilter] = useState("(all)");
  const [catFilter, setCatFilter] = useState("(all)");
  const [onlyFailures, setOnlyFailures] = useState(false);

  // Query detail modal.
  const [selectedQuery, setSelectedQuery] = useState<string | null>(null);
  const [queryDetail, setQueryDetail] = useState<QueryDetail | null>(null);

  // Compare.
  const [allRuns, setAllRuns] = useState<EvalRun[]>([]);
  const [compareRunId, setCompareRunId] = useState("");
  const [compareData, setCompareData] = useState<Record<string, unknown>[] | null>(null);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    fetchDashboard(runId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    fetchRuns().then(setAllRuns).catch(() => {});
  }, [runId]);

  useEffect(() => {
    if (selectedQuery && runId) {
      fetchQueryDetail(runId, selectedQuery)
        .then(setQueryDetail)
        .catch(console.error);
    } else {
      setQueryDetail(null);
    }
  }, [selectedQuery, runId]);

  useEffect(() => {
    if (compareRunId && runId) {
      compareRuns(compareRunId, runId)
        .then((r) => setCompareData(r.aggregate as Record<string, unknown>[]))
        .catch(console.error);
    } else {
      setCompareData(null);
    }
  }, [compareRunId, runId]);

  if (loading) return <div className="loading">Loading analytics…</div>;
  if (error) return <div className="alert alert-error">{error}</div>;
  if (!data) return <div className="alert alert-error">No data</div>;

  const { summary, query_rows, category, difficulty, documents, leaderboard, run } = data;
  const overall = summary.overall;

  // Metric keys.
  const allCoreMetrics = [
    { key: "recall", label: "Recall" },
    { key: "precision", label: "Precision" },
    { key: "f1", label: "F1" },
    { key: "exact_match", label: "Exact Match" },
    { key: "document_recall", label: "Doc Recall" },
    { key: "success_rate", label: "Success Rate" },
    { key: "semantic_similarity", label: "Semantic Sim." },
    { key: "llm_judge_score", label: "LLM Judge" },
    { key: "num_queries", label: "Queries" },
  ];

  // Filter to only metrics the user selected (always show success_rate and num_queries).
  const runSelectedMetrics: string[] | undefined = run.selected_metrics;
  const selectedSet = runSelectedMetrics && runSelectedMetrics.length > 0
    ? new Set([...runSelectedMetrics, "success_rate", "num_queries"])
    : null;
  const coreMetrics = selectedSet
    ? allCoreMetrics.filter((m) => selectedSet.has(m.key))
    : allCoreMetrics;

  const v1Names = new Set(allCoreMetrics.map((m) => m.key));
  const extraMetrics = Object.keys(overall).filter((k) => {
    if (v1Names.has(k)) return false;
    if (selectedSet && !selectedSet.has(k)) return false;
    return true;
  });

  // Filtered query rows.
  let filteredRows: QueryRow[] = [...query_rows];
  if (diffFilter !== "(all)") filteredRows = filteredRows.filter((r) => r.difficulty === diffFilter);
  if (catFilter !== "(all)") filteredRows = filteredRows.filter((r) => r.categories?.includes(catFilter));
  if (onlyFailures) filteredRows = filteredRows.filter((r) => !r.success);

  const allDifficulties = Array.from(new Set(query_rows.map((r) => r.difficulty).filter(Boolean))).sort();
  const allCategories = Array.from(new Set(query_rows.flatMap((r) => r.categories || []))).sort();

  // Failure taxonomy chart data.
  const failureData = Object.entries(summary.failure_counts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);

  // Category chart data.
  const catChartData = category.map((c) => ({
    name: c.scope_value,
    f1: typeof c.f1 === "number" ? c.f1 : 0,
  }));

  return (
    <>
      <button className="btn btn-secondary btn-sm" onClick={() => navigate("/analytics")}
        style={{ marginBottom: "1rem" }}>
        ← All Runs
      </button>

      <h1>Run Analytics</h1>
      <p className="subtitle" style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
        {run.run_id} &nbsp;|&nbsp; Dataset: {data.dataset_id} &nbsp;|&nbsp;
        Provider: {run.provider || "generic_http"} &nbsp;|&nbsp;
        <StatusBadge status={run.status} />
      </p>

      {/* Overall metrics */}
      <h2>Overall Metrics</h2>
      <div className="metrics-grid">
        {coreMetrics.map((m) => (
          <MetricCard
            key={m.key}
            label={m.label}
            value={overall[m.key]}
            format={m.key === "num_queries" ? "count" : "score"}
          />
        ))}
      </div>

      {extraMetrics.length > 0 && (
        <>
          <h3>Additional Metrics</h3>
          <div className="metrics-grid">
            {extraMetrics.map((k) => (
              <MetricCard key={k} label={k.replace(/_/g, " ")} value={overall[k]} />
            ))}
          </div>
        </>
      )}

      {/* Failure taxonomy */}
      {failureData.length > 0 && (
        <>
          <h2>Failure Taxonomy</h2>
          <div className="row">
            <div className="card" style={{ flex: 1 }}>
              <table className="data-table">
                <thead><tr><th>Failure Type</th><th>Count</th></tr></thead>
                <tbody>
                  {failureData.map((f) => (
                    <tr key={f.name}><td>{f.name}</td><td className="mono">{f.count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card" style={{ flex: 2, minHeight: 200 }}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={failureData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="name" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} />
                  <YAxis tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }} />
                  <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {/* Query-level results */}
      <h2>Query-Level Results</h2>
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem", flexWrap: "wrap", alignItems: "end" }}>
        <div className="form-group" style={{ marginBottom: 0, minWidth: 140 }}>
          <label>Difficulty</label>
          <select value={diffFilter} onChange={(e) => setDiffFilter(e.target.value)}>
            <option value="(all)">(all)</option>
            {allDifficulties.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div className="form-group" style={{ marginBottom: 0, minWidth: 140 }}>
          <label>Category</label>
          <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
            <option value="(all)">(all)</option>
            {allCategories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <label className="checkbox-item" style={{ marginBottom: 4 }}>
          <input type="checkbox" checked={onlyFailures} onChange={(e) => setOnlyFailures(e.target.checked)} />
          Only failures
        </label>
      </div>

      <div className="card" style={{ overflowX: "auto" }}>
        {(() => {
          const qCols: { key: keyof QueryRow; label: string }[] = [
            { key: "recall", label: "Recall" },
            { key: "precision", label: "Precision" },
            { key: "f1", label: "F1" },
            { key: "document_recall", label: "Doc Recall" },
            { key: "exact_match", label: "EM" },
          ];
          const activeQCols = selectedSet
            ? qCols.filter((c) => selectedSet.has(c.key as string))
            : qCols;
          return (
        <table className="data-table">
          <thead>
            <tr>
              <th>Query ID</th>
              <th>Difficulty</th>
              {activeQCols.map((c) => <th key={c.key as string}>{c.label}</th>)}
              <th>Success</th>
              <th>Failure</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.slice(0, 200).map((r) => (
              <tr key={r.query_id} className="clickable-row"
                onClick={() => setSelectedQuery(r.query_id)}>
                <td className="mono">{r.query_id}</td>
                <td><span className="tag">{r.difficulty}</span></td>
                {activeQCols.map((c) => (
                  <td key={c.key as string} className="mono">
                    {(r[c.key] as number)?.toFixed(3) ?? "—"}
                  </td>
                ))}
                <td>{r.success ? "✓" : "✗"}</td>
                <td>{r.failure_type !== "success" ? r.failure_type : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
          );
        })()}
        {filteredRows.length > 200 && (
          <p style={{ color: "var(--color-text-muted)", fontSize: "0.8rem", marginTop: "0.5rem" }}>
            Showing first 200 of {filteredRows.length} rows.
          </p>
        )}
      </div>

      {/* Query detail panel */}
      {selectedQuery && queryDetail && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3>Query: {selectedQuery}</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => setSelectedQuery(null)}>Close</button>
          </div>
          <div className="row" style={{ marginTop: "0.75rem" }}>
            <div>
              <h3>Query &amp; Ground Truth</h3>
              <p><strong>Query text:</strong> {String(queryDetail.query.query_text ?? queryDetail.query.query ?? "")}</p>
              <p><strong>GT answer(s):</strong> {JSON.stringify(queryDetail.query.gt_answers ?? queryDetail.query.gt_answer ?? "")}</p>
              {Boolean(queryDetail.query.gt_supporting_facts) && (
                <>
                  <strong>GT supporting facts:</strong>
                  <pre className="json-pre">{JSON.stringify(queryDetail.query.gt_supporting_facts, null, 2)}</pre>
                </>
              )}
            </div>
            <div>
              <h3>Metrics</h3>
              <pre className="json-pre">{JSON.stringify({
                ...Object.fromEntries(
                  ["recall", "precision", "f1", "document_recall", "exact_match",
                    "semantic_similarity", "llm_judge_score", "success", "failure_type",
                    "generated_answer"
                  ].map((k) => [k, queryDetail.metrics[k]])
                ),
                ...queryDetail.dynamic_metrics,
              }, null, 2)}</pre>
              <h3>Retrieved knowledge_state</h3>
              <pre className="json-pre">
                {JSON.stringify(queryDetail.raw_response?.knowledge_state ?? [], null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Category Analysis */}
      {category.length > 0 && (
        <>
          <h2>Category Analysis</h2>
          <div className="row">
            <div className="card" style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>F1</th>
                    <th>Recall</th>
                    <th>Precision</th>
                    <th>Success Rate</th>
                    <th>Queries</th>
                  </tr>
                </thead>
                <tbody>
                  {category.map((c) => (
                    <tr key={c.scope_value}>
                      <td>{c.scope_value}</td>
                      <td className="mono">{typeof c.f1 === "number" ? (c.f1 as number).toFixed(3) : "—"}</td>
                      <td className="mono">{typeof c.recall === "number" ? (c.recall as number).toFixed(3) : "—"}</td>
                      <td className="mono">{typeof c.precision === "number" ? (c.precision as number).toFixed(3) : "—"}</td>
                      <td className="mono">{typeof c.success_rate === "number" ? (c.success_rate as number).toFixed(3) : "—"}</td>
                      <td className="mono">{c.num_queries ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {catChartData.length > 0 && (
              <div className="card" style={{ minHeight: 200 }}>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={catChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="name" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} />
                    <YAxis domain={[0, 1]} tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }} />
                    <Bar dataKey="f1" fill="var(--color-success)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}

      {/* Difficulty */}
      {difficulty.length > 0 && (
        <>
          <h2>Difficulty Analysis</h2>
          <div className="card" style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr><th>Difficulty</th><th>F1</th><th>Recall</th><th>Success Rate</th><th>Queries</th></tr>
              </thead>
              <tbody>
                {difficulty.map((d) => (
                  <tr key={d.scope_value}>
                    <td>{d.scope_value}</td>
                    <td className="mono">{typeof d.f1 === "number" ? (d.f1 as number).toFixed(3) : "—"}</td>
                    <td className="mono">{typeof d.recall === "number" ? (d.recall as number).toFixed(3) : "—"}</td>
                    <td className="mono">{typeof d.success_rate === "number" ? (d.success_rate as number).toFixed(3) : "—"}</td>
                    <td className="mono">{d.num_queries ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Document analysis */}
      <h2>Document Analysis</h2>
      <div className="row">
        {(["most_retrieved", "most_missed", "failure_linked"] as const).map((key) => (
          <div className="card" key={key}>
            <div className="card-header">{key.replace(/_/g, " ")}</div>
            <table className="data-table">
              <thead><tr><th>Doc ID</th><th>Count</th></tr></thead>
              <tbody>
                {(documents[key] || []).slice(0, 10).map(([docId, count]) => (
                  <tr key={docId}><td className="mono">{docId}</td><td className="mono">{count}</td></tr>
                ))}
                {(!documents[key] || !documents[key].length) && (
                  <tr><td colSpan={2} style={{ color: "var(--color-text-muted)" }}>None</td></tr>
                )}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {/* Leaderboard */}
      {leaderboard.length > 0 && (
        <>
          <h2>Leaderboard Comparison</h2>
          <div className="card" style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr><th>System</th><th>Metric</th><th>Current Run</th><th>Baseline</th><th>Gap</th></tr>
              </thead>
              <tbody>
                {leaderboard.map((lb, i) => (
                  <tr key={i}>
                    <td>{lb.system_name}</td>
                    <td>{lb.metric}</td>
                    <td className="mono">{lb.current_run?.toFixed(4) ?? "—"}</td>
                    <td className="mono">{lb.leaderboard.toFixed(4)}</td>
                    <td className="mono" style={{ color: lb.gap != null ? (lb.gap >= 0 ? "var(--color-success)" : "var(--color-error)") : undefined }}>
                      {lb.gap != null ? (lb.gap >= 0 ? "+" : "") + lb.gap.toFixed(4) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Run comparison */}
      <h2>Compare With Another Run</h2>
      <div style={{ display: "flex", gap: "1rem", alignItems: "end", marginBottom: "1rem" }}>
        <div className="form-group" style={{ marginBottom: 0, minWidth: 300 }}>
          <label>Select run</label>
          <select value={compareRunId} onChange={(e) => setCompareRunId(e.target.value)}>
            <option value="">— none —</option>
            {allRuns.filter((r) => r.run_id !== runId).map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} [{r.provider}] ({r.status})
              </option>
            ))}
          </select>
        </div>
      </div>

      {compareData && compareData.length > 0 && (
        <div className="card" style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr><th>Metric</th><th>Other Run</th><th>This Run</th><th>Delta</th></tr>
            </thead>
            <tbody>
              {compareData.map((row, i) => (
                <tr key={i}>
                  <td>{String(row.metric)}</td>
                  <td className="mono">{row.run_a != null ? Number(row.run_a).toFixed(4) : "—"}</td>
                  <td className="mono">{row.run_b != null ? Number(row.run_b).toFixed(4) : "—"}</td>
                  <td className="mono" style={{
                    color: row.delta != null
                      ? (Number(row.delta) >= 0 ? "var(--color-success)" : "var(--color-error)")
                      : undefined
                  }}>
                    {row.delta != null ? (Number(row.delta) >= 0 ? "+" : "") + Number(row.delta).toFixed(4) : "—"}
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
