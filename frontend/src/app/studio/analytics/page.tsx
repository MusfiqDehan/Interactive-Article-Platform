"use client";

import { MousePointerClick, RefreshCw, Search, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageShell, QueryState } from "@/components/studio/PageShell";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { studioApi } from "@/lib/studio-api";

const RANGES = [7, 30, 90] as const;

interface Totals {
  views: number;
  unique_sessions: number;
  reads_completed: number;
  annotation_opens: number;
  hotspot_opens: number;
  media_plays: number;
  outbound_clicks: number;
  shares: number;
}

interface SiteAnalytics {
  days: number;
  totals: Totals;
  interaction_rate: number;
  completion_rate: number;
  series: Array<{
    day: string;
    views: number;
    annotation_opens: number;
    reads_completed: number;
  }>;
  top_articles: Array<{
    article_id: number;
    title: string;
    slug: string;
    views: number;
    annotation_opens: number;
    interaction_rate: number;
  }>;
}

export default function AnalyticsPage() {
  const [days, setDays] = useState<number>(30);
  const { data, loading, error, refresh } = useStudioQuery(async () => {
    const { data } = await studioApi().get<SiteAnalytics>("/analytics/", {
      params: { days },
    });
    return data;
  }, [days]);

  return (
    <PageShell
      title="Analytics"
      description="Measured from this site's own event stream — no third-party script, no cookies, and sessions that cannot be linked across days."
      actions={
        <div className="flex items-center gap-1">
          {RANGES.map((range) => (
            <button
              key={range}
              onClick={() => setDays(range)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition",
                days === range
                  ? "bg-[var(--sl-card)] text-white bg-[var(--sl-action)] text-[var(--sl-ink)]"
                  : "bg-[var(--sl-soft)] text-[var(--sl-ink)] bg-[var(--sl-card)]",
              )}
            >
              {range}d
            </button>
          ))}
          <Button size="icon" variant="ghost" onClick={refresh} aria-label="Refresh">
            <RefreshCw size={15} />
          </Button>
        </div>
      }
    >
      <QueryState loading={loading} error={error} isEmpty={false} empty={null}>
        {data && (
          <>
            {/* Interaction rate leads, deliberately. Views say the article was
                served; this says the interactive format was used -- and it is
                the number no generic analytics tool can produce. */}
            <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Headline
                label="Interaction rate"
                value={`${(data.interaction_rate * 100).toFixed(1)}%`}
                hint="Annotation opens per view"
                accent
                icon={MousePointerClick}
              />
              <Headline
                label="Views"
                value={data.totals.views.toLocaleString()}
                hint={`${data.totals.unique_sessions.toLocaleString()} unique sessions`}
                icon={TrendingUp}
              />
              <Headline
                label="Completion"
                value={`${(data.completion_rate * 100).toFixed(1)}%`}
                hint="Reached the end and stayed"
              />
              <Headline
                label="Annotation opens"
                value={data.totals.annotation_opens.toLocaleString()}
                hint={`${data.totals.media_plays.toLocaleString()} media plays`}
              />
            </div>

            <Sparkline series={data.series} />

            <h2 className="mb-2 mt-8 text-sm font-semibold text-[var(--sl-ink)]">
              Most read
            </h2>
            {data.top_articles.length === 0 ? (
              <p className="rounded-xl border border-dashed border-[var(--sl-line)] p-6 text-center text-sm text-[var(--sl-muted)]">
                No data yet for this range. Events are buffered and rolled up
                every few minutes.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
                <table className="w-full min-w-[560px] text-sm">
                  <thead className="border-b border-[var(--sl-line)] text-left text-xs uppercase tracking-wide text-[var(--sl-muted)]">
                    <tr>
                      <th className="px-4 py-2.5 font-medium">Article</th>
                      <th className="px-4 py-2.5 text-right font-medium">Views</th>
                      <th className="px-4 py-2.5 text-right font-medium">Opens</th>
                      <th className="px-4 py-2.5 text-right font-medium">Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--sl-line)]">
                    {data.top_articles.map((row) => (
                      <tr key={row.article_id}>
                        <td className="max-w-sm truncate px-4 py-2.5">
                          <Link
                            href={`/studio/content/${encodeURIComponent(row.slug)}`}
                            className="hover:underline"
                          >
                            {row.title}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">
                          {row.views.toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-[var(--sl-muted)]">
                          {row.annotation_opens.toLocaleString()}
                        </td>
                        <td
                          className={cn(
                            "px-4 py-2.5 text-right tabular-nums",
                            row.interaction_rate >= 0.2
                              ? "font-semibold text-emerald-600"
                              : row.interaction_rate < 0.05
                                ? "text-amber-600"
                                : "text-[var(--sl-muted)]",
                          )}
                        >
                          {(row.interaction_rate * 100).toFixed(0)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <SearchHealth />
          </>
        )}
      </QueryState>
    </PageShell>
  );
}

function Headline({
  label,
  value,
  hint,
  accent,
  icon: Icon,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: boolean;
  icon?: typeof TrendingUp;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        accent
          ? "border-[var(--sl-soft)] bg-[var(--sl-soft)] dark:bg-primary-950/40"
          : "border-[var(--sl-line)] bg-[var(--sl-card)]",
      )}
    >
      <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-[var(--sl-muted)]">
        {Icon && <Icon size={12} />} {label}
      </p>
      <p
        className={cn(
          "mt-1 font-display text-2xl font-bold tabular-nums",
          accent
            ? "text-[var(--sl-accent)]"
            : "text-[var(--sl-ink)]",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-xs text-[var(--sl-muted)]">{hint}</p>}
    </div>
  );
}

/** Views and annotation opens on the same scale, so the gap is the story. */
function Sparkline({
  series,
}: {
  series: Array<{ day: string; views: number; annotation_opens: number }>;
}) {
  if (series.length < 2) return null;
  const max = Math.max(...series.map((point) => point.views), 1);
  const width = 100;
  const height = 28;
  const path = (key: "views" | "annotation_opens") =>
    series
      .map((point, index) => {
        const x = (index / (series.length - 1)) * width;
        const y = height - (point[key] / max) * height;
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");

  return (
    <div className="rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-4">
      <div className="mb-2 flex items-center gap-4 text-xs">
        <span className="flex items-center gap-1.5 text-[var(--sl-muted)]">
          <span className="h-0.5 w-4 bg-[var(--sl-soft)]" /> Views
        </span>
        <span className="flex items-center gap-1.5 text-[var(--sl-muted)]">
          <span className="h-0.5 w-4 bg-[var(--sl-soft)]" /> Annotation opens
        </span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-24 w-full"
        role="img"
        aria-label="Views and annotation opens over time"
      >
        <path d={path("views")} fill="none" stroke="currentColor" strokeWidth="0.6" className="text-[var(--sl-muted)]" />
        <path
          d={path("annotation_opens")}
          fill="none"
          stroke="currentColor"
          strokeWidth="0.8"
          className="text-[var(--sl-accent)]"
        />
      </svg>
    </div>
  );
}

function SearchHealth() {
  const { data } = useStudioQuery(async () => {
    const { data } = await studioApi().get<{
      available: boolean;
      index: string;
      indexed: number;
      failed: number;
    }>("/search/health/");
    return data;
  }, []);

  if (!data) return null;
  return (
    <div className="mt-8 flex flex-wrap items-center gap-3 rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-4 text-sm">
      <Search size={15} className="text-[var(--sl-muted)]" />
      <span className="text-[var(--sl-ink)]">
        Search index <code className="text-xs">{data.index}</code>
      </span>
      {data.available ? (
        <span className="text-emerald-600">
          {data.indexed} indexed
          {data.failed > 0 && (
            // Not an outage: drift repair retries hourly. Worth surfacing so a
            // persistent failure is noticed before someone reports it.
            <span className="ml-1 text-amber-600">
              · {data.failed} awaiting repair
            </span>
          )}
        </span>
      ) : (
        <span className="text-amber-600">
          Unavailable — the site is serving normally; search will heal when it
          returns.
        </span>
      )}
    </div>
  );
}
