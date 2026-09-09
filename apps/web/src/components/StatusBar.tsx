"use client";

import { useDatasetStore } from "@/store/dataset";

const STEP_LABELS: Record<string, string> = {
  intake: "Intake",
  validation: "Validate",
  cleaning: "Clean",
  eda: "EDA",
  dashboard_builder: "Dashboard",
};

function StepDot({ step, stepStatus }: { step: string; stepStatus: string }) {
  const label = STEP_LABELS[step] || step;

  let dotCls = "bg-neutral-300 dark:bg-neutral-600";
  let textCls = "text-neutral-400 dark:text-neutral-500";

  if (stepStatus === "running") {
    dotCls = "bg-blue-500 animate-pulse";
    textCls = "text-blue-600 dark:text-blue-400 font-medium";
  } else if (stepStatus === "completed" || stepStatus === "succeeded") {
    dotCls = "bg-emerald-500";
    textCls = "text-emerald-600 dark:text-emerald-400";
  } else if (stepStatus === "failed") {
    dotCls = "bg-rose-500";
    textCls = "text-rose-600 dark:text-rose-400";
  }

  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-2 h-2 rounded-full shrink-0 ${dotCls}`} />
      <span className={`text-xs ${textCls}`}>{label}</span>
    </div>
  );
}

export default function StatusBar() {
  const { status, error, steps } = useDatasetStore();

  if (status === "idle") return null;

  const isRunning = status === "uploading" || status === "analyzing" || status === "polling";
  const isComplete = status === "completed";
  const isFailed = status === "failed";

  return (
    <div className="w-full">
      <div className={`rounded-lg px-4 py-3 border ${
        isComplete
          ? "bg-emerald-50 dark:bg-emerald-900/10 border-emerald-200 dark:border-emerald-800/40"
          : isFailed
            ? "bg-rose-50 dark:bg-rose-900/10 border-rose-200 dark:border-rose-800/40"
            : "bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800/40"
      }`}>
        <div className="flex items-center gap-2">
          {isRunning && (
            <svg className="w-3.5 h-3.5 animate-spin text-blue-500 shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          <p className={`text-sm font-medium ${
            isComplete ? "text-emerald-700 dark:text-emerald-400"
            : isFailed ? "text-rose-700 dark:text-rose-400"
            : "text-blue-700 dark:text-blue-400"
          }`}>
            {isComplete ? "Analysis complete" : isFailed ? "Analysis failed" : "Analyzing..."}
          </p>
        </div>

        {steps.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
            {steps.map((s) => (
              <StepDot key={s.node} step={s.node} stepStatus={s.status} />
            ))}
          </div>
        )}

        {error && (
          <p className="mt-2 text-xs text-rose-700 dark:text-rose-400 bg-rose-100 dark:bg-rose-900/20 rounded px-2 py-1.5">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
