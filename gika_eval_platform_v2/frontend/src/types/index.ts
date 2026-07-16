/* ------------------------------------------------------------------ */
/* Types mirroring the FastAPI response shapes                        */
/* ------------------------------------------------------------------ */

export interface Dataset {
  dataset_id: string;
  name: string;
  version: string;
  domain: string;
  source: string;
  created_at: string;
  query_count: number;
}

export interface UploadResult {
  dataset_id: string;
  name: string;
  version: string;
  format: string;
  total_items: number;
  preview: PreviewRow[];
  capability_report: CapabilityReport;
  validation_warnings: string[];
  parse_warnings: string[];
  detected_columns: string[];
}

export interface PreviewRow {
  query_id: string;
  query: string;
  gt_answer: string;
  difficulty: string;
  categories: string[];
  facts_count: number;
  docs_count: number;
}

export interface CapabilityReport {
  status: string;
  detected_fields: string[];
  missing_fields: string[];
  warnings: string[];
  errors: string[];
  supported_metrics: string[];
  unsupported_metrics: string[];
  field_coverage: Record<string, number>;
}

export interface MetricDefinition {
  name: string;
  display_name: string;
  category: string;
  description: string;
  required_fields: string[];
}

export interface EvalRun {
  run_id: string;
  dataset_id: string;
  dataset_version: string;
  run_name: string;
  provider: string;
  api_endpoint: string;
  status: string;
  total_queries: number;
  started_at: string | null;
  finished_at: string | null;
  comparison_group_id: string;
  selected_metrics?: string[];
}

export interface RunSummary {
  overall: Record<string, number | null>;
  success_rate: number;
  failure_counts: Record<string, number>;
}

export interface DashboardData {
  run: EvalRun;
  dataset_id: string;
  summary: RunSummary;
  query_rows: QueryRow[];
  difficulty: ScopeRow[];
  category: ScopeRow[];
  documents: DocumentAnalysis;
  leaderboard: LeaderboardRow[];
}

export interface QueryRow {
  query_id: string;
  difficulty: string;
  categories: string[];
  eval_label: string;
  recall: number | null;
  precision: number | null;
  f1: number | null;
  document_recall: number | null;
  exact_match: number | null;
  semantic_similarity: number | null;
  llm_judge_score: number | null;
  success: boolean | null;
  failure_type: string | null;
}

export interface ScopeRow {
  scope_value: string;
  [metric: string]: string | number | null;
}

export interface DocumentAnalysis {
  most_retrieved: [string, number][];
  most_missed: [string, number][];
  failure_linked: [string, number][];
}

export interface LeaderboardRow {
  system_name: string;
  metric: string;
  current_run: number | null;
  leaderboard: number;
  gap: number | null;
}

export interface QueryDetail {
  query: Record<string, unknown>;
  metrics: Record<string, unknown>;
  raw_response: Record<string, unknown>;
  dynamic_metrics: Record<string, number | null>;
}

export interface CompareResult {
  group_id: string;
  system_a: { run_id: string; name: string; summary: Record<string, unknown> };
  system_b: { run_id: string; name: string; summary: Record<string, unknown> };
  aggregate: CompareRow[];
  per_query: Record<string, unknown>[];
}

export interface CompareRow {
  metric: string;
  run_a: number | null;
  run_b: number | null;
  delta: number | null;
}

export interface ProvidersInfo {
  providers: string[];
  default: string;
}

export interface GTMergeResult {
  success: boolean;
  matched_count: number;
  unmatched_gt_ids: string[];
  missing_dataset_ids: string[];
  warnings: string[];
  updated_capability_report: CapabilityReport;
}
