"use client";

import type { OutputData } from "@editorjs/editorjs";
import { AlertCircle, Check, Loader2, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { SnippetPreview } from "@/components/studio/SnippetPreview";
import { studioApi } from "@/lib/studio-api";

interface CheckRow {
  id: string;
  label: string;
  status: "pass" | "warn" | "fail";
  message: string;
  weight?: number;
}

interface Analysis {
  score: number;
  checks: CheckRow[];
  resolved_seo: {
    meta_title?: string;
    meta_description?: string;
    focus_keyword?: string;
    canonical_url?: string;
  };
}

const DEBOUNCE_MS = 500;

/**
 * Live SEO sidebar.
 *
 * Scores the **unsaved draft**, not the last saved revision: the endpoint
 * accepts the in-progress title/excerpt/content and skips caching for them.
 * Scoring the stored copy instead would show a number that lags the text on
 * screen by one save, which is exactly when an editor stops trusting it.
 */
export function SeoPanel({
  slug,
  title,
  excerpt,
  blocks,
  siteUrl,
}: {
  slug: string;
  title: string;
  excerpt: string;
  blocks: OutputData | undefined;
  siteUrl: string;
}) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestRef = useRef({ title, excerpt, blocks });
  latestRef.current = { title, excerpt, blocks };

  const analyze = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const { title: t, excerpt: e, blocks: b } = latestRef.current;
      const { data } = await studioApi().post<Analysis>(
        `/articles/${encodeURIComponent(slug)}/analyze-seo/`,
        { title: t, excerpt: e, content: { blocks: b?.blocks ?? [] } },
      );
      setAnalysis(data);
    } catch {
      setError("Could not score this draft.");
    } finally {
      setPending(false);
    }
  }, [slug]);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(analyze, DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [analyze, title, excerpt, blocks]);

  const seo = analysis?.resolved_seo ?? {};
  const failing = (analysis?.checks ?? []).filter((c) => c.status !== "pass");
  const passing = (analysis?.checks ?? []).filter((c) => c.status === "pass");

  return (
    <div className="space-y-5">
      <SnippetPreview
        title={seo.meta_title || title}
        description={seo.meta_description || excerpt}
        url={seo.canonical_url || siteUrl || "https://example.com/articles/…"}
      />

      <div className="flex items-center gap-3 rounded-lg border border-[var(--sl-line)] p-3">
        <ScoreDial score={analysis?.score ?? 0} pending={pending && !analysis} />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--sl-ink)]">
            {analysis ? `${analysis.score}/100` : "Scoring…"}
          </p>
          <p className="text-xs text-[var(--sl-muted)]">
            {failing.length === 0 && analysis
              ? "All checks passing."
              : `${failing.length} issue${failing.length === 1 ? "" : "s"} to fix`}
          </p>
        </div>
        {pending && analysis && (
          <Loader2 size={14} className="ml-auto animate-spin text-[var(--sl-muted)]" />
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {failing.length > 0 && (
        <ul className="space-y-1.5">
          {failing.map((check) => (
            <li key={check.id} className="flex items-start gap-2 text-sm">
              {check.status === "fail" ? (
                <XCircle size={14} className="mt-0.5 shrink-0 text-red-500" />
              ) : (
                <AlertCircle size={14} className="mt-0.5 shrink-0 text-amber-500" />
              )}
              <span className="min-w-0">
                <span className="block text-[var(--sl-ink)]">
                  {check.label}
                </span>
                <span className="block text-xs text-[var(--sl-muted)]">{check.message}</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {passing.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
            {passing.length} passing
          </summary>
          <ul className="mt-2 space-y-1">
            {passing.map((check) => (
              <li key={check.id} className="flex items-start gap-2">
                <Check size={14} className="mt-0.5 shrink-0 text-emerald-600" />
                <span className="text-[var(--sl-ink)]">{check.label}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function ScoreDial({ score, pending }: { score: number; pending: boolean }) {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);
  const colour = score >= 80 ? "#10b981" : score >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <svg width="44" height="44" viewBox="0 0 44 44" className="shrink-0" aria-hidden="true">
      <circle
        cx="22"
        cy="22"
        r={radius}
        fill="none"
        strokeWidth="4"
        className="stroke-slate-200 dark:stroke-slate-700"
      />
      {!pending && (
        <circle
          cx="22"
          cy="22"
          r={radius}
          fill="none"
          strokeWidth="4"
          stroke={colour}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 22 22)"
          style={{ transition: "stroke-dashoffset 300ms ease" }}
        />
      )}
    </svg>
  );
}
