"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useDatasetStore } from "@/store/dataset";
import { useAuthStore } from "@/store/auth";
import { shareDataset, unshareDataset, previewDataset, analyzeDataset, type PreviewResponse } from "@/lib/api";
import Dashboard from "@/components/Dashboard";
import ColumnProfiles from "@/components/ColumnProfiles";

function DataPreview({ preview }: { preview: PreviewResponse }) {
  const [expanded, setExpanded] = useState(false);
  const visibleRows = expanded ? preview.rows : preview.rows.slice(0, 10);

  return (
    <div className="rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-50">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">Data Preview</p>
          <p className="text-[11px] text-gray-300 mt-0.5">
            Showing {visibleRows.length} of {preview.total_rows?.toLocaleString()} rows
          </p>
        </div>
        {preview.rows.length > 10 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-indigo-500 hover:text-indigo-700 font-medium"
          >
            {expanded ? "Show less" : `Show all ${preview.rows.length}`}
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-50">
              {preview.columns.map((col) => (
                <th key={col} className="px-3 py-2 text-left font-medium text-gray-500 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, i) => (
              <tr key={i} className="border-t border-gray-50 hover:bg-gray-50/50">
                {preview.columns.map((col) => (
                  <td key={col} className="px-3 py-1.5 text-gray-600 whitespace-nowrap max-w-[200px] truncate">
                    {row[col] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="rounded-2xl p-8 bg-gradient-to-r from-gray-50 to-gray-100">
        <div className="h-6 bg-gray-200 rounded w-32 mb-3" />
        <div className="h-10 bg-gray-200 rounded w-48 mb-2" />
        <div className="h-4 bg-gray-100 rounded w-96 mt-4" />
        <div className="h-4 bg-gray-100 rounded w-80 mt-2" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl p-4 border border-gray-100 bg-white">
            <div className="h-3 bg-gray-100 rounded w-24 mb-2" />
            <div className="h-5 bg-gray-200 rounded w-16" />
          </div>
        ))}
      </div>
      <div className="rounded-xl p-4 border border-gray-100 bg-white">
        <div className="h-3 bg-gray-100 rounded w-32 mb-3" />
        <div className="h-48 bg-gray-50 rounded" />
      </div>
    </div>
  );
}

export default function DatasetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const datasetId = params.id as string;

  const { isAuthenticated, hydrated, email, logout, hydrate } = useAuthStore();
  const { status, dashboardSpec, loadExisting, reset } = useDatasetStore();
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!datasetId) return;
    loadExisting(datasetId);
    return () => { reset(); };
  }, [datasetId, loadExisting, reset]);

  const handleShare = async () => {
    setSharing(true);
    setActionError(null);
    try {
      const res = await shareDataset(datasetId);
      setShareToken(res.share_token);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to share");
    } finally {
      setSharing(false);
    }
  };

  const handleUnshare = async () => {
    setActionError(null);
    try {
      await unshareDataset(datasetId);
      setShareToken(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to unshare");
    }
  };

  const handleCopy = () => {
    if (!shareToken) return;
    const url = `${window.location.origin}/shared/${shareToken}`;
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePreview = async () => {
    if (preview) {
      setShowPreview(!showPreview);
      return;
    }
    try {
      const res = await previewDataset(datasetId);
      setPreview(res);
      setShowPreview(true);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to load preview");
    }
  };

  const handleReanalyze = async () => {
    setReanalyzing(true);
    try {
      const res = await analyzeDataset(datasetId);
      useDatasetStore.setState({
        datasetId,
        runId: res.run_id,
        status: "polling",
        error: null,
        dashboardSpec: null,
        columnProfiles: null,
        steps: [],
      });
      router.push("/");
      setTimeout(() => useDatasetStore.getState().pollStatus(), 500);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to start re-analysis");
    } finally {
      setReanalyzing(false);
    }
  };

  if (!hydrated) {
    return (
      <main className="min-h-screen bg-[#FAFAF8] flex items-center justify-center">
        <div className="animate-pulse text-sm text-gray-400">Loading...</div>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <main className="min-h-screen bg-[#FAFAF8] flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-gray-500 text-sm">Please log in to view this dataset.</p>
          <button
            onClick={() => router.push("/login")}
            className="px-4 py-2 rounded-lg bg-indigo-500 text-white text-sm font-medium hover:bg-indigo-600 transition-colors"
          >
            Log in
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#FAFAF8] text-gray-900">
      <header className="sticky top-0 z-20 bg-[#FAFAF8]/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1
              className="text-base font-bold tracking-tight text-gray-800 cursor-pointer"
              onClick={() => router.push("/")}
            >
              CortexBI
            </h1>
            <span className="text-gray-200">/</span>
            <button
              onClick={() => router.push("/datasets")}
              className="text-xs font-medium text-gray-400 hover:text-gray-700 transition-colors"
            >
              Datasets
            </button>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">{email}</span>
            <button
              onClick={() => { logout(); router.push("/login"); }}
              className="text-xs font-medium text-gray-400 hover:text-gray-700 transition-colors px-2 py-1 rounded-lg hover:bg-gray-100"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {status === "completed" && dashboardSpec && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handlePreview}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors shadow-sm"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              {showPreview ? "Hide Data" : "View Data"}
            </button>

            <button
              onClick={handleReanalyze}
              disabled={reanalyzing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors shadow-sm disabled:opacity-50"
            >
              <svg className={`w-3.5 h-3.5 ${reanalyzing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {reanalyzing ? "Re-analyzing..." : "Re-analyze"}
            </button>

            {!shareToken ? (
              <button
                onClick={handleShare}
                disabled={sharing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors shadow-sm disabled:opacity-50"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                </svg>
                {sharing ? "..." : "Share"}
              </button>
            ) : (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200 text-xs font-medium text-indigo-600 hover:bg-indigo-100 transition-colors"
                >
                  {copied ? "Copied!" : "Copy Link"}
                </button>
                <button
                  onClick={handleUnshare}
                  className="px-2 py-1.5 rounded-lg text-xs text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                  title="Revoke share link"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )}
          </div>
        )}

        {actionError && (
          <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{actionError}</p>
        )}

        {showPreview && preview && <DataPreview preview={preview} />}

        {status === "polling" && <DashboardSkeleton />}

        {status === "failed" && (
          <div className="text-center py-20">
            <p className="text-red-500 text-sm">Failed to load dashboard</p>
            <div className="flex items-center justify-center gap-3 mt-3">
              <button
                onClick={() => loadExisting(datasetId)}
                className="px-4 py-2 rounded-lg bg-indigo-500 text-white text-sm font-medium hover:bg-indigo-600 transition-colors"
              >
                Retry
              </button>
              <button
                onClick={handleReanalyze}
                disabled={reanalyzing}
                className="px-4 py-2 rounded-lg bg-amber-500 text-white text-sm font-medium hover:bg-amber-600 transition-colors disabled:opacity-50"
              >
                {reanalyzing ? "Re-analyzing..." : "Re-analyze"}
              </button>
              <button
                onClick={() => router.push("/datasets")}
                className="px-4 py-2 rounded-lg bg-gray-100 text-gray-600 text-sm hover:bg-gray-200 transition-colors"
              >
                Back to datasets
              </button>
            </div>
          </div>
        )}

        {status === "completed" && dashboardSpec && (
          <>
            <Dashboard />
            <ColumnProfiles />
          </>
        )}
      </div>
    </main>
  );
}
