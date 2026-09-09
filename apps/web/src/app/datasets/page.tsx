"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { listDatasets, deleteDataset, type DatasetSummary } from "@/lib/api";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  completed: { bg: "bg-emerald-50", text: "text-emerald-600", label: "Ready" },
  analyzing: { bg: "bg-amber-50", text: "text-amber-600", label: "Analyzing" },
  uploaded: { bg: "bg-gray-50", text: "text-gray-500", label: "Uploaded" },
  failed: { bg: "bg-red-50", text: "text-red-500", label: "Failed" },
};

function SkeletonRow() {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl border border-gray-100 bg-white shadow-sm animate-pulse">
      <div className="space-y-2 flex-1">
        <div className="h-4 bg-gray-100 rounded w-48" />
        <div className="h-3 bg-gray-50 rounded w-64" />
      </div>
      <div className="h-4 w-4 bg-gray-100 rounded" />
    </div>
  );
}

export default function DatasetsPage() {
  const router = useRouter();
  const { isAuthenticated, hydrated, email, logout, hydrate } = useAuthStore();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!isAuthenticated) return;
    setLoading(true);
    setListError(null);
    listDatasets()
      .then(setDatasets)
      .catch((err) => setListError(err instanceof Error ? err.message : "Failed to load datasets"))
      .finally(() => setLoading(false));
  }, [isAuthenticated]);

  const filtered = datasets.filter((ds) =>
    ds.filename.toLowerCase().includes(search.toLowerCase())
  );

  const handleDelete = async (e: React.MouseEvent, datasetId: string) => {
    e.stopPropagation();
    if (!window.confirm("Delete this dataset and all its analyses?")) return;
    setDeleting(datasetId);
    try {
      await deleteDataset(datasetId);
      setDatasets((prev) => prev.filter((d) => d.dataset_id !== datasetId));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete dataset");
    } finally {
      setDeleting(null);
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
          <p className="text-gray-500 text-sm">Please log in to view your datasets.</p>
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
          <h1
            className="text-base font-bold tracking-tight text-gray-800 cursor-pointer"
            onClick={() => router.push("/")}
          >
            CortexBI
          </h1>
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

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-800">Your Datasets</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              {search && filtered.length !== datasets.length
                ? `${filtered.length} of ${datasets.length} analyses`
                : `${datasets.length} analyses`}
            </p>
          </div>
          <button
            onClick={() => router.push("/")}
            className="px-4 py-2 rounded-lg bg-indigo-500 text-white text-sm font-medium hover:bg-indigo-600 transition-colors"
          >
            New Analysis
          </button>
        </div>

        {datasets.length > 3 && (
          <div className="mb-4">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search datasets..."
              className="w-full max-w-sm px-3 py-2 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition-colors"
            />
          </div>
        )}

        {listError && (
          <div className="text-center py-8">
            <p className="text-red-500 text-sm">{listError}</p>
          </div>
        )}

        {loading ? (
          <div className="space-y-2">
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-400 text-sm">
              {search ? "No datasets match your search." : "No datasets yet."}
            </p>
            {!search && <p className="text-gray-300 text-xs mt-1">Upload a CSV to get started.</p>}
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((ds) => {
              const status = ds.latest_run?.status === "completed" ? "completed"
                : ds.latest_run?.status === "running" ? "analyzing"
                : ds.status;
              const style = STATUS_STYLES[status] || STATUS_STYLES.uploaded;
              const canView = ds.latest_run?.status === "completed";
              const isDeleting = deleting === ds.dataset_id;

              return (
                <div
                  key={ds.dataset_id}
                  role={canView ? "button" : undefined}
                  tabIndex={canView ? 0 : undefined}
                  onClick={() => canView && router.push(`/datasets/${ds.dataset_id}`)}
                  onKeyDown={(e) => {
                    if (canView && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      router.push(`/datasets/${ds.dataset_id}`);
                    }
                  }}
                  className={`flex items-center justify-between p-4 rounded-xl border border-gray-100 bg-white shadow-sm transition-all ${
                    canView ? "cursor-pointer hover:shadow-md hover:border-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-200" : ""
                  } ${isDeleting ? "opacity-50" : ""}`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-800 truncate">
                        {ds.filename}
                      </p>
                      <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold ${style.bg} ${style.text}`}>
                        {style.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-[11px] text-gray-400">
                      <span>{ds.row_count?.toLocaleString()} rows</span>
                      <span>{ds.column_count} columns</span>
                      <span>{formatDate(ds.uploaded_at)}</span>
                      <span>{formatTime(ds.uploaded_at)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 ml-3">
                    <button
                      onClick={(e) => handleDelete(e, ds.dataset_id)}
                      disabled={isDeleting}
                      className="p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors"
                      title="Delete dataset"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                    {canView && (
                      <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
