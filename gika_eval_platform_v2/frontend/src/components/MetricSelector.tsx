import { useEffect, useState } from "react";
import { fetchMetrics } from "../services/api";
import type { MetricDefinition } from "../types";

interface Props {
  supportedMetrics?: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export default function MetricSelector({ supportedMetrics, selected, onChange }: Props) {
  const [metrics, setMetrics] = useState<MetricDefinition[]>([]);

  useEffect(() => {
    fetchMetrics().then(setMetrics).catch(console.error);
  }, []);

  const toggle = (name: string) => {
    if (selected.includes(name)) {
      onChange(selected.filter((n) => n !== name));
    } else {
      onChange([...selected, name]);
    }
  };

  const retrieval = metrics.filter((m) => m.category === "retrieval");
  const answer = metrics.filter((m) => m.category === "answer");

  const renderGroup = (title: string, items: MetricDefinition[]) => (
    <div>
      <h3>{title}</h3>
      <div className="checkbox-group">
        {items.map((m) => {
          const available = !supportedMetrics || supportedMetrics.includes(m.name);
          return (
            <label
              key={m.name}
              className={`checkbox-item ${!available ? "disabled" : ""}`}
              title={m.description}
            >
              <input
                type="checkbox"
                checked={selected.includes(m.name)}
                disabled={!available}
                onChange={() => toggle(m.name)}
              />
              {m.display_name}
              {!available && " ⚠️"}
            </label>
          );
        })}
      </div>
    </div>
  );

  if (!metrics.length) return <div className="loading">Loading metrics…</div>;

  return (
    <div className="card" style={{ marginBottom: "1rem" }}>
      <div className="card-header">Select Metrics</div>
      <div className="row">
        {renderGroup("Retrieval", retrieval)}
        {renderGroup("Answer", answer)}
      </div>
      {supportedMetrics && (
        <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: "0.5rem" }}>
          ⚠️ = unavailable (dataset missing required ground-truth data)
        </p>
      )}
    </div>
  );
}
