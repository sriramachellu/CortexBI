"use client";

import React, { useEffect, useRef, useState } from "react";
import { useDatasetStore } from "@/store/dataset";
import { useExport } from "@/lib/useExport";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import type { ChartSpec, StoryInsight, StorySection, ModelMetrics, Domain } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Domain color palettes — pastel, warm, product-designer style      */
/* ------------------------------------------------------------------ */

const DOMAIN_THEMES: Record<string, {
  accent: string; accentSoft: string; heroBg: string;
  heroGradient: string; cardBorder: string; badge: string; badgeText: string;
}> = {
  sales:     { accent: "#6366F1", accentSoft: "#EEF2FF", heroBg: "#F5F3FF", heroGradient: "linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 50%, #FDF2F8 100%)", cardBorder: "#E0E7FF", badge: "#EEF2FF", badgeText: "#4338CA" },
  marketing: { accent: "#10B981", accentSoft: "#ECFDF5", heroBg: "#F0FDF4", heroGradient: "linear-gradient(135deg, #ECFDF5 0%, #F0FDF4 50%, #F0FDFA 100%)", cardBorder: "#D1FAE5", badge: "#ECFDF5", badgeText: "#047857" },
  people:    { accent: "#A855F7", accentSoft: "#FAF5FF", heroBg: "#FAF5FF", heroGradient: "linear-gradient(135deg, #FAF5FF 0%, #FDF4FF 50%, #FFF1F2 100%)", cardBorder: "#E9D5FF", badge: "#FAF5FF", badgeText: "#7C3AED" },
  finance:   { accent: "#F97316", accentSoft: "#FFF7ED", heroBg: "#FFFBEB", heroGradient: "linear-gradient(135deg, #FFF7ED 0%, #FFFBEB 50%, #FEF3C7 100%)", cardBorder: "#FED7AA", badge: "#FFF7ED", badgeText: "#C2410C" },
  general:   { accent: "#3B82F6", accentSoft: "#EFF6FF", heroBg: "#F0F9FF", heroGradient: "linear-gradient(135deg, #EFF6FF 0%, #F0F9FF 50%, #F5F3FF 100%)", cardBorder: "#BFDBFE", badge: "#EFF6FF", badgeText: "#1D4ED8" },
};

const CHART_COLORS = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4", "#F97316"];

const SENTIMENT_STYLES: Record<string, { bg: string; border: string; dot: string }> = {
  positive: { bg: "#F0FDF4", border: "#BBF7D0", dot: "#22C55E" },
  negative: { bg: "#FFF1F2", border: "#FECDD3", dot: "#F43F5E" },
  neutral:  { bg: "#F8FAFC", border: "#E2E8F0", dot: "#94A3B8" },
};

/* ------------------------------------------------------------------ */
/*  Shared formatting                                                 */
/* ------------------------------------------------------------------ */

function formatKPIValue(value: string | number, format?: string): string {
  if (typeof value === "string") return value;
  if (format === "currency") {
    if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
    return `$${value.toFixed(2)}`;
  }
  if (format === "percent") return `${(value * 100).toFixed(1)}%`;
  if (format === "integer") return Math.round(value).toLocaleString();
  if (Number.isInteger(value)) {
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toLocaleString();
  }
  return value.toFixed(2);
}

/* ------------------------------------------------------------------ */
/*  Hero section                                                      */
/* ------------------------------------------------------------------ */

function StoryHeroSection({ hero, domain }: {
  hero: { headline: string; big_number: string; big_number_label: string; big_number_context?: string; summary: string };
  domain: Domain;
}) {
  const theme = DOMAIN_THEMES[domain] || DOMAIN_THEMES.general;
  return (
    <section
      className="rounded-2xl p-6 sm:p-8"
      style={{ background: theme.heroGradient }}
    >
      <div className="flex flex-col sm:flex-row sm:items-start gap-6">
        <div className="shrink-0">
          <p className="text-[11px] font-semibold uppercase tracking-widest mb-1" style={{ color: theme.accent }}>
            {domain === "general" ? "Key Finding" : domain}
          </p>
          <p className="text-4xl sm:text-5xl font-extrabold tracking-tight text-gray-900">
            {hero.big_number}
          </p>
          <p className="text-sm text-gray-500 mt-0.5">{hero.big_number_label}</p>
          {hero.big_number_context && (
            <p className="text-xs text-gray-400 mt-0.5">{hero.big_number_context}</p>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 leading-snug">
            {hero.headline}
          </h2>
          <p className="text-sm text-gray-600 mt-2 leading-relaxed max-w-2xl">
            {hero.summary}
          </p>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Insight cards                                                     */
/* ------------------------------------------------------------------ */

function InsightCard({ insight }: { insight: StoryInsight }) {
  const style = SENTIMENT_STYLES[insight.sentiment] || SENTIMENT_STYLES.neutral;
  return (
    <div
      className="rounded-xl p-4 border transition-shadow hover:shadow-md"
      style={{ backgroundColor: style.bg, borderColor: style.border }}
    >
      <div className="flex items-start gap-3">
        <span
          className="w-2 h-2 rounded-full mt-1.5 shrink-0"
          style={{ backgroundColor: style.dot }}
        />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-800 leading-snug">
            {insight.finding}
          </p>
          <p className="text-xs text-gray-500 mt-1">{insight.detail}</p>
          <div className="flex items-baseline gap-1.5 mt-2">
            <span className="text-lg font-bold text-gray-900 tabular-nums">
              {insight.metric_value}
            </span>
            <span className="text-[11px] text-gray-400 uppercase tracking-wide">
              {insight.metric_label}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Chart rendering                                                   */
/* ------------------------------------------------------------------ */

function formatAxisValue(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

const TOOLTIP_STYLE = {
  backgroundColor: "#ffffff",
  border: "1px solid #E5E7EB",
  borderRadius: "10px",
  color: "#1F2937",
  fontSize: 12,
  padding: "8px 12px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
};

function truncateLabel(label: string, max: number): string {
  return label.length > max ? label.slice(0, max - 1) + "…" : label;
}

function renderChart(spec: ChartSpec, accentColor: string) {
  const { type, data, x, y, series } = spec;
  const gridColor = "#F3F4F6";
  const axisColor = "#9CA3AF";
  const manyPoints = data.length > 10;
  const hasLongLabels = data.some(d => String(d[x] || "").length > 12);
  const xAxisProps = hasLongLabels || manyPoints
    ? { angle: -35, textAnchor: "end" as const, fontSize: 10, height: 70, tickFormatter: (v: string) => truncateLabel(String(v), 14) }
    : { fontSize: 11, tickFormatter: (v: string) => truncateLabel(String(v), 20) };

  switch (type) {
    case "bar":
    case "histogram":
      return (
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: hasLongLabels || manyPoints ? 30 : 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey={x} tick={xAxisProps} stroke={axisColor} tickLine={false} axisLine={false} interval={manyPoints ? "preserveStartEnd" : 0} />
          <YAxis tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} width={50} tickFormatter={formatAxisValue} />
          <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(99,102,241,0.06)" }} />
          <Bar dataKey={y || "value"} fill={accentColor} radius={[6, 6, 0, 0]} maxBarSize={48} fillOpacity={0.85} />
        </BarChart>
      );

    case "grouped_bar":
      return (
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: hasLongLabels || manyPoints ? 30 : 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey={x} tick={xAxisProps} stroke={axisColor} tickLine={false} axisLine={false} interval={manyPoints ? "preserveStartEnd" : 0} />
          <YAxis tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} width={50} tickFormatter={formatAxisValue} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconSize={8} />
          {(series || []).map((key, i) => (
            <Bar key={key} dataKey={key} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[4, 4, 0, 0]} maxBarSize={36} fillOpacity={0.85} />
          ))}
        </BarChart>
      );

    case "stacked_bar":
      return (
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: hasLongLabels || manyPoints ? 30 : 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey={x} tick={xAxisProps} stroke={axisColor} tickLine={false} axisLine={false} interval={manyPoints ? "preserveStartEnd" : 0} />
          <YAxis tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} width={50} tickFormatter={formatAxisValue} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconSize={8} />
          {(series || []).map((key, i) => (
            <Bar key={key} dataKey={key} stackId="stack" fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.85} />
          ))}
        </BarChart>
      );

    case "line":
      return (
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: hasLongLabels || manyPoints ? 30 : 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey={x} tick={xAxisProps} stroke={axisColor} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} width={50} tickFormatter={formatAxisValue} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          {(series || [y || "value"]).map((key, i) => (
            <Line key={key} type="monotone" dataKey={key as string} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2.5} dot={data.length <= 30} activeDot={{ r: 5, strokeWidth: 2, fill: "#fff" }} />
          ))}
          {(series || []).length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} iconSize={8} />}
        </LineChart>
      );

    case "area":
      return (
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: hasLongLabels || manyPoints ? 30 : 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey={x} tick={xAxisProps} stroke={axisColor} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} width={50} tickFormatter={formatAxisValue} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          {(series || [y || "value"]).map((key, i) => (
            <Area key={key} type="monotone" dataKey={key as string} stroke={CHART_COLORS[i % CHART_COLORS.length]} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.12} strokeWidth={2} />
          ))}
        </AreaChart>
      );

    case "scatter":
      return (
        <ScatterChart margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey={x} name={x} tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} />
          <YAxis dataKey={y || "value"} name={y || "value"} tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} width={50} tickFormatter={formatAxisValue} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Scatter data={data} fill={accentColor} fillOpacity={0.6} />
        </ScatterChart>
      );

    case "pie": {
      const PASTEL_PIE = ["#818CF8", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#F472B6", "#22D3EE", "#FB923C"];
      return (
        <PieChart>
          <Pie data={data} dataKey={y || "value"} nameKey={x} cx="50%" cy="50%" outerRadius="70%" innerRadius="40%" paddingAngle={3} strokeWidth={2} stroke="#fff">
            {data.map((_, i) => <Cell key={i} fill={PASTEL_PIE[i % PASTEL_PIE.length]} />)}
          </Pie>
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Legend wrapperStyle={{ fontSize: 11, lineHeight: "1.6" }} iconSize={8} iconType="circle" />
        </PieChart>
      );
    }

    case "feature_importance":
      return (
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis type="number" tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey={y || "feature"} tick={{ fontSize: 11 }} stroke={axisColor} tickLine={false} axisLine={false} width={110} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Bar dataKey={x || "importance"} fill={accentColor} radius={[0, 6, 6, 0]} maxBarSize={20} fillOpacity={0.85} />
        </BarChart>
      );

    default:
      return (
        <BarChart data={data}>
          <Bar dataKey={y || "value"} fill={accentColor} radius={[6, 6, 0, 0]} />
        </BarChart>
      );
  }
}

/* ------------------------------------------------------------------ */
/*  Story section (narrative + chart)                                  */
/* ------------------------------------------------------------------ */

function StorySectionBlock({ section, index, accentColor }: {
  section: StorySection; index: number; accentColor: string;
}) {
  const isEven = index % 2 === 0;
  return (
    <section className="space-y-4">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 mb-1">
          Part {index + 1}
        </p>
        <h3 className="text-lg font-bold text-gray-900">{section.title}</h3>
        <p className="text-sm text-gray-600 mt-1.5 leading-relaxed max-w-2xl">
          {section.narrative}
        </p>
      </div>
      {section.chart && (
        <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
          <p className="text-xs font-medium text-gray-500 mb-3">{section.chart.title}</p>
          <div className="h-56 sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              {renderChart(section.chart, accentColor)}
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Recommendations                                                   */
/* ------------------------------------------------------------------ */

function RecommendationsSection({ items, accentColor }: { items: string[]; accentColor: string }) {
  if (!items || items.length === 0) return null;
  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3">
        What you should do
      </h3>
      <ul className="space-y-3">
        {items.map((rec, i) => (
          <li key={i} className="flex items-start gap-3">
            <span
              className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-white text-[10px] font-bold"
              style={{ backgroundColor: accentColor }}
            >
              {i + 1}
            </span>
            <p className="text-sm text-gray-700 leading-relaxed">{rec}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Model summary (ML insights — for deep dive)                       */
/* ------------------------------------------------------------------ */

function ModelSummaryCard({ metrics, accentColor }: { metrics: ModelMetrics; accentColor: string }) {
  const isClassification = metrics.task === "classification";
  const scoreValue = isClassification ? metrics.accuracy : metrics.r2_score;
  const scoreFormatted = scoreValue != null ? (scoreValue * 100).toFixed(0) + "%" : "N/A";
  const quality = scoreValue != null
    ? scoreValue >= 0.9 ? "Excellent" : scoreValue >= 0.7 ? "Good" : scoreValue >= 0.5 ? "Fair" : "Poor"
    : "N/A";
  const targetLabel = metrics.target?.replace(/_/g, " ") || "target";
  const taskLabel = isClassification ? "classifying" : "predicting";

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 mb-1">
            Prediction Model
          </p>
          <p className="text-sm text-gray-700">
            CortexBI built a model for {taskLabel} <span className="font-semibold text-gray-900">{targetLabel}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-extrabold tabular-nums text-gray-900">{scoreFormatted}</p>
          <p className="text-xs font-semibold" style={{ color: accentColor }}>{quality}</p>
        </div>
      </div>
      <div className="flex gap-4 mt-3 text-[11px] text-gray-400">
        <span>Trained on {metrics.train_size} rows</span>
        <span>Tested on {metrics.test_size} rows</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Deep dive (collapsed)                                              */
/* ------------------------------------------------------------------ */

function DeepDiveSection({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <section>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 rounded-xl border border-gray-100 bg-white text-left hover:bg-gray-50 transition-colors shadow-sm"
      >
        <span className="text-sm font-semibold text-gray-600">
          {open ? "Hide" : "View"} detailed analysis
        </span>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="mt-3 space-y-3">{children}</div>}
    </section>
  );
}

function KPIRow({ kpis }: { kpis: { label: string; value: string | number; format?: string; comparison_text?: string }[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {kpis.map((kpi, i) => (
        <div key={i} className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 truncate">
            {kpi.label.replace(/_/g, " ")}
          </p>
          <p className="text-xl font-bold mt-1 tabular-nums text-gray-900">{formatKPIValue(kpi.value, kpi.format)}</p>
          {kpi.comparison_text && (
            <p className="text-[11px] text-gray-400 mt-0.5">{kpi.comparison_text}</p>
          )}
        </div>
      ))}
    </div>
  );
}

interface CorrelationPair { col1: string; col2: string; correlation: number }

function CorrelationsBlock({ correlations }: { correlations: Record<string, unknown> }) {
  const pairs = (correlations.top_pairs || []) as CorrelationPair[];
  const count = correlations.strong_pair_count as number | undefined;
  if (!pairs.length) return null;
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 mb-3">
        Correlations <span className="text-gray-300 font-normal">{count} strong</span>
      </p>
      <div className="space-y-2">
        {pairs.map((p, i) => {
          const color = p.correlation > 0 ? "#22C55E" : "#F43F5E";
          return (
            <div key={i} className="flex items-center justify-between text-sm gap-2">
              <span className="text-gray-600 truncate min-w-0">
                {p.col1.replace(/_/g, " ")} &harr; {p.col2.replace(/_/g, " ")}
              </span>
              <div className="flex items-center gap-2 shrink-0">
                <div className="w-14 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.abs(p.correlation) * 100}%`, backgroundColor: color }} />
                </div>
                <span className="font-mono text-xs font-medium w-12 text-right" style={{ color }}>
                  {p.correlation > 0 ? "+" : ""}{p.correlation.toFixed(2)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DataQualityBlock({ quality }: { quality: Record<string, unknown> }) {
  const labels: Record<string, string> = {
    rows_total: "Total Rows", columns_total: "Total Columns",
    duplicates_removed: "Duplicates Removed", columns_with_missing: "Columns with Missing Data",
    columns_with_outliers: "Columns with Outliers",
  };
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 mb-3">Data Quality</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {Object.entries(quality).map(([key, val]) => (
          <div key={key}>
            <span className="text-[11px] text-gray-400">{labels[key] || key.replace(/_/g, " ")}</span>
            <p className="text-lg font-bold tabular-nums text-gray-900">{String(val)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Dashboard                                                     */
/* ------------------------------------------------------------------ */

interface ExportBarProps {
  containerRef: React.RefObject<HTMLDivElement>;
}

function ExportBar({ containerRef }: ExportBarProps) {
  const { exporting, exportDashboard } = useExport();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const handle = (format: "png" | "pdf") => {
    setOpen(false);
    if (containerRef.current) exportDashboard(containerRef.current, format);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        disabled={!!exporting}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors disabled:opacity-50 shadow-sm"
      >
        {exporting ? (
          <span>Exporting {exporting.toUpperCase()}...</span>
        ) : (
          <>
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white rounded-lg border border-gray-200 shadow-lg py-1 z-30 min-w-[120px]">
          <button onClick={() => handle("png")} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50">
            Download PNG
          </button>
          <button onClick={() => handle("pdf")} className="w-full text-left px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50">
            Download PDF
          </button>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const { dashboardSpec } = useDatasetStore();
  const dashRef = useRef<HTMLDivElement>(null);
  if (!dashboardSpec) return null;

  const {
    domain = "general",
    hero,
    insights,
    story_sections,
    recommendations,
    kpis,
    charts,
    data_quality,
    correlations_summary,
    model_metrics,
    feature_importance_chart,
    // Legacy v3 fields
    title,
    subtitle,
    ai_insights,
  } = dashboardSpec;

  const theme = DOMAIN_THEMES[domain] || DOMAIN_THEMES.general;
  const isStoryMode = !!hero;

  // ---- Story Mode (v4) ----
  if (isStoryMode) {
    return (
      <div className="w-full space-y-6">
        <div className="flex justify-end">
          <ExportBar containerRef={dashRef} />
        </div>
        <div ref={dashRef} className="space-y-6">
        {/* Hero */}
        <StoryHeroSection hero={hero} domain={domain as Domain} />

        {/* Insight cards */}
        {insights && insights.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {insights.slice(0, 4).map((insight, i) => (
              <InsightCard key={i} insight={insight} />
            ))}
          </div>
        )}

        {/* Story sections */}
        {story_sections && story_sections.length > 0 && (
          <div className="space-y-8">
            {story_sections.map((section, i) => (
              <StorySectionBlock key={i} section={section} index={i} accentColor={theme.accent} />
            ))}
          </div>
        )}

        {/* Recommendations */}
        {recommendations && recommendations.length > 0 && (
          <RecommendationsSection items={recommendations} accentColor={theme.accent} />
        )}

        {/* Deep Dive */}
        <DeepDiveSection>
          {kpis && kpis.length > 0 && <KPIRow kpis={kpis} />}

          {model_metrics && (
            <ModelSummaryCard metrics={model_metrics} accentColor={theme.accent} />
          )}

          {feature_importance_chart && (
            <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400 mb-1">{feature_importance_chart.title}</p>
              {feature_importance_chart.insight && (
                <p className="text-xs text-gray-400 mb-3">{feature_importance_chart.insight}</p>
              )}
              <div className="h-72 sm:h-80">
                <ResponsiveContainer width="100%" height="100%">
                  {renderChart(feature_importance_chart, theme.accent)}
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {correlations_summary && Number((correlations_summary as Record<string, unknown>).strong_pair_count ?? 0) > 0 && (
            <CorrelationsBlock correlations={correlations_summary as Record<string, unknown>} />
          )}

          {data_quality && <DataQualityBlock quality={data_quality} />}
        </DeepDiveSection>
        </div>
      </div>
    );
  }

  // ---- Legacy mode (v3 fallback) ----
  return (
    <div className="w-full space-y-5">
      {title && (
        <div>
          <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
          {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
      )}
      {ai_insights && (
        <div className="rounded-xl bg-indigo-50 p-4 border border-indigo-100">
          <p className="text-sm text-indigo-800 leading-relaxed">{ai_insights}</p>
        </div>
      )}
      {kpis && kpis.length > 0 && <KPIRow kpis={kpis} />}
      {charts && charts.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {charts.map((chart, i) => (
            <div key={i} className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-gray-500 mb-2">{chart.title}</p>
              <div className="h-48 sm:h-56">
                <ResponsiveContainer width="100%" height="100%">
                  {renderChart(chart, CHART_COLORS[0])}
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
