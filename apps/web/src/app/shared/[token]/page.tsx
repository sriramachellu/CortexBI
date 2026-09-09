"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getSharedDashboard, type DashboardSpec } from "@/lib/api";
import { useDatasetStore } from "@/store/dataset";
import Dashboard from "@/components/Dashboard";

export default function SharedDashboardPage() {
  const params = useParams();
  const token = params.token as string;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filename, setFilename] = useState("");

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getSharedDashboard(token)
      .then((res) => {
        useDatasetStore.setState({
          dashboardSpec: res.dashboard_spec,
          status: "completed",
        });
        setFilename(res.filename);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"))
      .finally(() => setLoading(false));
    return () => { useDatasetStore.getState().reset(); };
  }, [token]);

  if (loading) {
    return (
      <main className="min-h-screen bg-[#FAFAF8] flex items-center justify-center">
        <div className="text-sm text-gray-400">Loading shared dashboard...</div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-[#FAFAF8] flex items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-red-500 text-sm">This shared link is invalid or has been revoked.</p>
          <p className="text-gray-400 text-xs">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#FAFAF8] text-gray-900">
      <header className="sticky top-0 z-20 bg-[#FAFAF8]/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <h1 className="text-base font-bold tracking-tight text-gray-800">CortexBI</h1>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-500 font-medium">Shared</span>
            <span>{filename}</span>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <Dashboard />
      </div>
    </main>
  );
}
