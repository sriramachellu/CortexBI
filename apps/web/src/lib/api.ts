function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("cortexbi_token");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("cortexbi_token");
      localStorage.removeItem("cortexbi_user");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

// --- Auth ---

export interface AuthResponse {
  token: string;
  user_id: string;
  email: string;
}

export async function signup(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

// --- Datasets ---

export interface UploadResponse {
  dataset_id: string;
  filename: string;
  size_bytes: number;
  row_count: number;
  column_count: number;
  status: string;
}

export interface DatasetSummary {
  dataset_id: string;
  filename: string;
  row_count: number | null;
  column_count: number | null;
  status: string;
  uploaded_at: string;
  latest_run: {
    run_id: string;
    status: string;
    completed_at: string | null;
  } | null;
}

export interface AnalyzeResponse {
  run_id: string;
  status: string;
}

export interface StepStatus {
  node: string;
  status: string;
  started_at?: string;
  ended_at?: string;
}

export interface RunStatus {
  run_id: string;
  status: string;
  steps: StepStatus[];
  error_message?: string;
}

export interface RunSummary {
  run_id: string;
  status: string;
  created_at: string;
}

export interface KPI {
  label: string;
  value: string | number;
  change?: string;
  format?: "number" | "currency" | "percent" | "integer";
  comparison_text?: string;
}

export interface ChartSpec {
  title: string;
  type: "bar" | "grouped_bar" | "stacked_bar" | "line" | "area" | "histogram" | "scatter" | "pie" | "feature_importance";
  x: string;
  y?: string;
  series?: string[];
  data: Record<string, unknown>[];
  insight?: string;
}

export interface ModelMetrics {
  task: "regression" | "classification";
  target: string;
  accuracy?: number;
  r2_score?: number;
  n_features: number;
  train_size: number;
  test_size: number;
  n_classes?: number;
}

export interface StoryHero {
  headline: string;
  big_number: string;
  big_number_label: string;
  big_number_context?: string;
  summary: string;
}

export interface StoryInsight {
  finding: string;
  detail: string;
  sentiment: "positive" | "negative" | "neutral";
  metric_value: string;
  metric_label: string;
}

export interface StorySection {
  title: string;
  narrative: string;
  chart: ChartSpec | null;
}

export type Domain = "sales" | "marketing" | "people" | "finance" | "general";

export interface DashboardSpec {
  spec_version?: string;
  domain?: Domain;
  hero?: StoryHero;
  insights?: StoryInsight[];
  story_sections?: StorySection[];
  recommendations?: string[];
  title?: string;
  subtitle?: string;
  kpis: KPI[];
  charts: ChartSpec[];
  data_quality?: Record<string, unknown>;
  correlations_summary?: Record<string, unknown>;
  ai_insights?: string;
  ai_driven?: boolean;
  model_metrics?: ModelMetrics | null;
  feature_importance_chart?: ChartSpec | null;
}

export interface DashboardResponse {
  dashboard_spec: DashboardSpec;
  column_profiles: Record<string, unknown>[];
  run_id: string;
}

export function listDatasets(): Promise<DatasetSummary[]> {
  return request<DatasetSummary[]>("/api/datasets");
}

export function uploadDataset(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/api/datasets/upload", {
    method: "POST",
    body: form,
  });
}

export function analyzeDataset(datasetId: string): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>(`/api/datasets/${datasetId}/analyze`, {
    method: "POST",
  });
}

export function getRunStatus(
  datasetId: string,
  runId: string
): Promise<RunStatus> {
  return request<RunStatus>(
    `/api/datasets/${datasetId}/runs/${runId}/status`
  );
}

export function getDashboard(datasetId: string): Promise<DashboardResponse> {
  return request<DashboardResponse>(`/api/datasets/${datasetId}/dashboard`);
}

export function listRuns(datasetId: string): Promise<RunSummary[]> {
  return request<RunSummary[]>(`/api/datasets/${datasetId}/runs`);
}

// --- Preview ---

export interface PreviewResponse {
  columns: string[];
  rows: Record<string, string>[];
  total_rows: number | null;
  total_columns: number | null;
}

export function previewDataset(datasetId: string): Promise<PreviewResponse> {
  return request<PreviewResponse>(`/api/datasets/${datasetId}/preview`);
}

// --- Delete ---

export function deleteDataset(datasetId: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/api/datasets/${datasetId}`, { method: "DELETE" });
}

// --- Share ---

export function shareDataset(datasetId: string): Promise<{ share_token: string }> {
  return request<{ share_token: string }>(`/api/datasets/${datasetId}/share`, { method: "POST" });
}

export function unshareDataset(datasetId: string): Promise<{ unshared: boolean }> {
  return request<{ unshared: boolean }>(`/api/datasets/${datasetId}/share`, { method: "DELETE" });
}

// --- Shared (public, no auth) ---

export interface SharedDashboardResponse {
  dashboard_spec: DashboardSpec;
  filename: string;
  row_count: number | null;
  column_count: number | null;
}

export function getSharedDashboard(shareToken: string): Promise<SharedDashboardResponse> {
  return request<SharedDashboardResponse>(`/api/shared/${shareToken}/dashboard`);
}
