interface Props {
  status: string;
}

const classMap: Record<string, string> = {
  completed: "badge-success",
  ready: "badge-success",
  running: "badge-info",
  pending: "badge-pending",
  partial: "badge-warning",
  incomplete: "badge-warning",
  failed: "badge-error",
  invalid: "badge-error",
};

export default function StatusBadge({ status }: Props) {
  const cls = classMap[status?.toLowerCase()] ?? "badge-pending";
  return <span className={`badge ${cls}`}>{status}</span>;
}
