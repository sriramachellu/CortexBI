"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDatasetStore } from "@/store/dataset";
import { useAuthStore } from "@/store/auth";
import FileUpload from "@/components/FileUpload";
import StatusBar from "@/components/StatusBar";
import Dashboard from "@/components/Dashboard";
import ColumnProfiles from "@/components/ColumnProfiles";

export default function Home() {
  const router = useRouter();
  const { status, dashboardSpec, reset } = useDatasetStore();
  const { isAuthenticated, hydrated, email, logout, hydrate } = useAuthStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const showUpload = status === "idle";
  const showStatus = status !== "idle";
  const showDashboard = status === "completed" && dashboardSpec;

  return (
    <main className="min-h-screen bg-[#FAFAF8] text-gray-900">
      <header className="sticky top-0 z-20 bg-[#FAFAF8]/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <h1 className="text-base font-bold tracking-tight text-gray-800">CortexBI</h1>
          <div className="flex items-center gap-2">
            {hydrated && isAuthenticated && (
              <>
                <button
                  onClick={() => router.push("/datasets")}
                  className="text-xs font-medium text-gray-400 hover:text-gray-700 transition-colors px-2 py-1 rounded-lg hover:bg-gray-100"
                >
                  My Datasets
                </button>
                <span className="text-xs text-gray-300">{email}</span>
                <button
                  onClick={() => { logout(); router.push("/login"); }}
                  className="text-xs font-medium text-gray-400 hover:text-gray-700 transition-colors px-2 py-1 rounded-lg hover:bg-gray-100"
                >
                  Log out
                </button>
              </>
            )}
            {hydrated && !isAuthenticated && (
              <button
                onClick={() => router.push("/login")}
                className="text-xs font-medium text-indigo-500 hover:text-indigo-700 transition-colors px-2.5 py-1 rounded-lg hover:bg-indigo-50"
              >
                Log in
              </button>
            )}
            {status !== "idle" && (
              <button
                onClick={reset}
                className="text-xs font-medium text-gray-400 hover:text-gray-700 transition-colors px-2.5 py-1 rounded-lg hover:bg-gray-100"
              >
                New Analysis
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {showUpload && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6">
            <div className="text-center space-y-2">
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-800">Upload your dataset</h2>
              <p className="text-sm text-gray-400 max-w-md mx-auto">
                Drop a CSV file to get a story-mode analysis with actionable insights
              </p>
            </div>
            <FileUpload />
          </div>
        )}

        {showStatus && !showDashboard && <StatusBar />}

        {showDashboard && (
          <>
            <Dashboard />
            <ColumnProfiles />
          </>
        )}
      </div>
    </main>
  );
}
