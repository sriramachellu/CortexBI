import { create } from "zustand";
import {
  uploadDataset,
  analyzeDataset,
  getRunStatus,
  getDashboard,
  type DashboardSpec,
  type StepStatus,
} from "@/lib/api";

type Status =
  | "idle"
  | "uploading"
  | "analyzing"
  | "polling"
  | "completed"
  | "failed";

interface DatasetState {
  datasetId: string | null;
  runId: string | null;
  status: Status;
  error: string | null;
  dashboardSpec: DashboardSpec | null;
  columnProfiles: Record<string, unknown>[] | null;
  steps: StepStatus[];
  _pollTimer: ReturnType<typeof setTimeout> | null;
  upload: (file: File) => Promise<void>;
  analyze: () => Promise<void>;
  pollStatus: () => Promise<void>;
  fetchDashboard: () => Promise<void>;
  loadExisting: (datasetId: string) => Promise<void>;
  reset: () => void;
}

const POLL_INTERVAL = 2000;

export const useDatasetStore = create<DatasetState>((set, get) => ({
  datasetId: null,
  runId: null,
  status: "idle",
  error: null,
  dashboardSpec: null,
  columnProfiles: null,
  steps: [],
  _pollTimer: null,

  upload: async (file: File) => {
    set({ status: "uploading", error: null });
    try {
      const res = await uploadDataset(file);
      set({ datasetId: res.dataset_id, status: "uploading" });
      await get().analyze();
    } catch (err) {
      set({
        status: "failed",
        error: err instanceof Error ? err.message : "Upload failed",
      });
    }
  },

  analyze: async () => {
    const { datasetId } = get();
    if (!datasetId) return;
    set({ status: "analyzing", error: null });
    try {
      const res = await analyzeDataset(datasetId);
      set({ runId: res.run_id, status: "polling" });
      get().pollStatus();
    } catch (err) {
      set({
        status: "failed",
        error: err instanceof Error ? err.message : "Analysis failed",
      });
    }
  },

  pollStatus: async () => {
    const { datasetId, runId } = get();
    if (!datasetId || !runId) return;

    let errorCount = 0;
    const MAX_RETRIES = 5;

    const poll = async () => {
      const current = get();
      if (current.status === "idle" || current.runId !== runId) return;

      try {
        const res = await getRunStatus(datasetId, runId);
        errorCount = 0;
        set({ steps: res.steps || [] });

        if (res.status === "completed") {
          set({ status: "completed", _pollTimer: null });
          await get().fetchDashboard();
          return;
        }
        if (res.status === "failed") {
          set({ status: "failed", error: res.error_message || "Pipeline failed", _pollTimer: null });
          return;
        }
        const timer = setTimeout(poll, POLL_INTERVAL);
        set({ _pollTimer: timer });
      } catch (err) {
        errorCount++;
        if (errorCount >= MAX_RETRIES) {
          set({
            status: "failed",
            error: err instanceof Error ? err.message : "Polling failed",
            _pollTimer: null,
          });
          return;
        }
        const timer = setTimeout(poll, POLL_INTERVAL * 2);
        set({ _pollTimer: timer });
      }
    };

    poll();
  },

  fetchDashboard: async () => {
    const { datasetId } = get();
    if (!datasetId) return;
    try {
      const res = await getDashboard(datasetId);
      set({
        dashboardSpec: res.dashboard_spec,
        columnProfiles: res.column_profiles,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load dashboard",
      });
    }
  },

  loadExisting: async (datasetId: string) => {
    set({ datasetId, status: "polling", error: null });
    try {
      const res = await getDashboard(datasetId);
      set({
        dashboardSpec: res.dashboard_spec,
        columnProfiles: res.column_profiles,
        runId: res.run_id,
        status: "completed",
      });
    } catch (err) {
      set({
        status: "failed",
        error: err instanceof Error ? err.message : "Failed to load dashboard",
      });
    }
  },

  reset: () => {
    const { _pollTimer } = get();
    if (_pollTimer) clearTimeout(_pollTimer);
    set({
      datasetId: null,
      runId: null,
      status: "idle",
      error: null,
      dashboardSpec: null,
      columnProfiles: null,
      steps: [],
      _pollTimer: null,
    });
  },
}));
