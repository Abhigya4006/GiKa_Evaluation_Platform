interface Props {
  label: string;
  value: number | null | undefined;
  format?: "score" | "count" | "percent";
}

export default function MetricCard({ label, value, format = "score" }: Props) {
  let display = "—";
  if (value != null) {
    if (format === "count") display = String(Math.round(value));
    else if (format === "percent") display = `${(value * 100).toFixed(1)}%`;
    else display = value.toFixed(3);
  }

  return (
    <div className="metric-card">
      <div className="label">{label}</div>
      <div className="value">{display}</div>
    </div>
  );
}
