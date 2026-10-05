"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled route error:", error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center px-4 text-center">
      <h1 className="font-display text-2xl font-bold text-slate-900 dark:text-slate-100">
        Something went wrong
      </h1>
      <p className="mt-3 text-slate-600 dark:text-slate-400">
        This page failed to load. Trying again may be enough.
      </p>
      {error.digest && (
        <p className="mt-2 font-mono text-xs text-slate-400">
          Reference: {error.digest}
        </p>
      )}
      <button type="button" onClick={reset} className="btn-primary mt-8">
        Try again
      </button>
    </div>
  );
}
