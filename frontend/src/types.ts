export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "rejected"
  | "timed_out"
  | "cancelled"
  | "failed";
export interface Bound {
  max_correct: number;
  total: number;
  fraction: string;
  value: number;
}
export interface Summary {
  graph_count: number;
  node_count: number;
  class_count: number;
  training_accuracy_upper_bound: Bound;
  unavoidable_training_errors: number;
  conflicting_pair_count: number;
  certificate_verified: boolean;
  engine?: "trace" | "partition";
}
export interface Job {
  id: string;
  status: JobStatus;
  progress: {
    round: number | null;
    step?: number | null;
    color_count: number;
  } | null;
  summary: Summary | null;
  error: { code: string; message: string } | null;
  expires_at: number | null;
  runtime_seconds: number;
  peak_memory_mb: number;
}
export interface Graph {
  id: string;
  nodes: { id: string; features: number[] }[];
  edges: [string, string][];
}
export interface Round {
  round: number;
  palette: unknown[];
  node_colors: number[][];
  histograms: [number, number][][];
}
export interface WLClass {
  id: string;
  graph_ids: string[];
  size: number;
  max_correct: number;
  unavoidable_errors: number;
  label_counts: { count: number }[];
}
export interface View {
  dataset: { graphs: Graph[]; feature_dtype: string; feature_dim: number };
  report: { classes: WLClass[]; certificate: { rounds?: Round[] } };
  inspection?: { mode: "rounds" | "stable_only"; rounds?: Round[] };
  graph_label_text: Record<string, string>;
  class_label_text: Record<string, string[]>;
}
export interface Config {
  limits: {
    max_bytes: number;
    max_graphs: number;
    max_nodes: number;
    max_edges: number;
    max_feature_dim: number;
    timeout_seconds: number;
    ttl_seconds: number;
  };
  scope: string;
  storage: string;
}
export const isActive = (job: Job | null) =>
  job?.status === "queued" || job?.status === "running";
export const percent = (bound: Bound) => {
  const displayed = Number((bound.value * 100).toFixed(2));
  return displayed === 100 && bound.max_correct < bound.total
    ? "<100%"
    : `${displayed}%`;
};
