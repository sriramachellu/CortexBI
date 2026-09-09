"use client";

import { useState } from "react";
import { useDatasetStore } from "@/store/dataset";

interface ColumnProfile {
  column_name: string;
  dtype: string;
  missing_pct: number | null;
  missing_count: number | null;
  unique_count: number | null;
  mean: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
  has_outliers?: boolean;
}

function formatNum(val: number | null | undefined): string {
  if (val === undefined || val === null) return "—";
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (Math.abs(val) >= 10_000) return `${(val / 1_000).toFixed(1)}K`;
  if (Number.isInteger(val)) return val.toLocaleString();
  return val.toFixed(2);
}

function DtypeBadge({ dtype }: { dtype: string }) {
  const colors: Record<string, string> = {
    int64: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
    float64: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
    bool: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    str: "bg-neutral-100 text-neutral-600 dark:bg-neutral-700/60 dark:text-neutral-300",
    object: "bg-neutral-100 text-neutral-600 dark:bg-neutral-700/60 dark:text-neutral-300",
  };
  const cls = colors[dtype] || colors.object;
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${cls}`}>
      {dtype}
    </span>
  );
}

export default function ColumnProfiles() {
  const { columnProfiles } = useDatasetStore();
  const [open, setOpen] = useState(false);

  if (!columnProfiles || columnProfiles.length === 0) return null;

  const profiles = columnProfiles as unknown as ColumnProfile[];

  return (
    <div className="w-full bg-white dark:bg-neutral-800/80 rounded-lg border border-neutral-200 dark:border-neutral-700/60 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-neutral-50 dark:hover:bg-neutral-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Column Profiles
          </h3>
          <span className="text-[10px] font-normal bg-neutral-100 dark:bg-neutral-700 text-neutral-500 dark:text-neutral-400 px-1.5 py-0.5 rounded">
            {profiles.length} columns
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-neutral-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead>
              <tr className="border-t border-b border-neutral-200 dark:border-neutral-700/60 text-left">
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 sticky left-0 bg-white dark:bg-neutral-800/80 z-10">
                  Column
                </th>
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">Type</th>
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 text-right">Missing</th>
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 text-right">Unique</th>
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 text-right">Mean</th>
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 text-right">Std</th>
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 text-right">Min</th>
                <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 text-right">Max</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 dark:divide-neutral-700/40">
              {profiles.map((col) => {
                const missingPct = col.missing_pct ?? 0;
                const hasMissing = missingPct > 0;
                return (
                  <tr key={col.column_name} className="hover:bg-neutral-50 dark:hover:bg-neutral-700/20 transition-colors">
                    <td className="px-3 py-2 font-medium text-sm sticky left-0 bg-white dark:bg-neutral-800/80 z-10">
                      <div className="flex items-center gap-2">
                        <span className="truncate max-w-[140px]">{col.column_name}</span>
                        {col.has_outliers && (
                          <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-amber-500" title="Has outliers" />
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2"><DtypeBadge dtype={col.dtype} /></td>
                    <td className={`px-3 py-2 text-right tabular-nums text-xs ${hasMissing ? "text-rose-600 dark:text-rose-400 font-medium" : "text-neutral-400 dark:text-neutral-500"}`}>
                      {missingPct.toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{col.unique_count ?? "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{formatNum(col.mean)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{formatNum(col.std)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{formatNum(col.min)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{formatNum(col.max)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
