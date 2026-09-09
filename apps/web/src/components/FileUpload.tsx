"use client";

import { useCallback, useState, useRef } from "react";
import { useDatasetStore } from "@/store/dataset";

const MAX_FILE_SIZE_MB = 50;

export default function FileUpload() {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { upload, status } = useDatasetStore();

  const handleFile = useCallback((file: File) => {
    setFileError(null);
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setFileError("Only CSV files are supported.");
      return;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setFileError(`File is too large. Maximum size is ${MAX_FILE_SIZE_MB} MB.`);
      return;
    }
    setSelectedFile(file);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onUpload = useCallback(() => {
    if (selectedFile) {
      upload(selectedFile);
    }
  }, [selectedFile, upload]);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const isUploading = status === "uploading";

  return (
    <div className="w-full max-w-md mx-auto">
      <div
        role="button"
        tabIndex={0}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={`border-2 border-dashed rounded-lg p-8 sm:p-10 text-center cursor-pointer transition-all focus:outline-none focus:ring-2 focus:ring-indigo-200 ${
          dragOver
            ? "border-indigo-500 bg-indigo-500/5 scale-[1.01]"
            : "border-gray-300 hover:border-indigo-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={onChange}
          className="hidden"
        />
        <svg
          className="w-10 h-10 mx-auto text-gray-400 mb-3"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        <p className="text-sm text-gray-600">
          Drag and drop a CSV file, or <span className="text-indigo-600 font-medium">browse</span>
        </p>
        <p className="text-xs text-gray-400 mt-1">
          .csv up to {MAX_FILE_SIZE_MB} MB
        </p>
      </div>

      {fileError && (
        <p className="mt-2 text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{fileError}</p>
      )}

      {selectedFile && (
        <div className="mt-3 p-3 bg-white border border-gray-200 rounded-lg flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium text-sm truncate text-gray-800">{selectedFile.name}</p>
            <p className="text-xs text-gray-500">{formatSize(selectedFile.size)}</p>
          </div>
          <button
            onClick={onUpload}
            disabled={isUploading}
            className="shrink-0 px-4 py-2 bg-indigo-500 text-white text-sm font-medium rounded-lg hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isUploading ? "Uploading..." : "Upload & Analyze"}
          </button>
        </div>
      )}
    </div>
  );
}
