"use client";

import { CalendarClock, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageShell, QueryState } from "@/components/studio/PageShell";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { getCalendar, scheduleArticle, type CalendarEntry } from "@/lib/studio-api";

/**
 * Publishing calendar.
 *
 * Dragging an article onto a day reschedules it, keeping the **time of day it
 * already had**. An editor moving a post from Tuesday to Thursday means "same
 * slot, different day"; resetting to midnight would silently retime a carefully
 * chosen 09:00 publication, and nothing on screen would say so. Items dragged
 * in from the unscheduled rail have no time yet and get 09:00, which is a
 * choice made once and visible in the cell rather than a hidden default.
 */

const DEFAULT_HOUR = 9;
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const KIND_STYLE: Record<CalendarEntry["kind"], string> = {
  scheduled_publish:
    "border-blue-300 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200",
  scheduled_unpublish:
    "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200",
  published:
    "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200",
};

export default function CalendarPage() {
  const [monthStart, setMonthStart] = useState(() => startOfMonth(new Date()));
  const [dragging, setDragging] = useState<CalendarEntry | null>(null);
  const [overDay, setOverDay] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const grid = useMemo(() => monthGrid(monthStart), [monthStart]);
  const { data, loading, error: loadError, refresh } = useStudioQuery(
    () => getCalendar(grid[0], addDays(grid[grid.length - 1], 1)),
    [monthStart.toISOString()],
  );

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarEntry[]>();
    for (const entry of data?.entries ?? []) {
      if (!entry.at) continue;
      const key = dayKey(new Date(entry.at));
      map.set(key, [...(map.get(key) ?? []), entry]);
    }
    return map;
  }, [data]);

  const drop = async (day: Date) => {
    const entry = dragging;
    setDragging(null);
    setOverDay(null);
    if (!entry) return;

    const previous = entry.scheduled_publish_at ?? entry.published_at;
    const when = new Date(day);
    if (previous) {
      const old = new Date(previous);
      when.setHours(old.getHours(), old.getMinutes(), 0, 0);
    } else {
      when.setHours(DEFAULT_HOUR, 0, 0, 0);
    }

    if (when.getTime() <= Date.now()) {
      setError("That date has already passed — pick a future day.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await scheduleArticle(entry.slug, { scheduled_publish_at: when.toISOString() });
      refresh();
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, string[]> } }).response
        ?.data;
      setError(
        data ? Object.values(data).flat().join(" ") : "Could not reschedule that.",
      );
    } finally {
      setBusy(false);
    }
  };

  const monthLabel = monthStart.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  return (
    <PageShell
      title="Calendar"
      description="Drag an article onto a day to reschedule it. Its time of day is kept."
      actions={
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            aria-label="Previous month"
            onClick={() => setMonthStart(addMonths(monthStart, -1))}
          >
            <ChevronLeft size={16} />
          </Button>
          <span className="w-40 text-center text-sm font-semibold text-[var(--sl-ink)]">
            {monthLabel}
          </span>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Next month"
            onClick={() => setMonthStart(addMonths(monthStart, 1))}
          >
            <ChevronRight size={16} />
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setMonthStart(startOfMonth(new Date()))}
          >
            Today
          </Button>
        </div>
      }
    >
      {(error || busy) && (
        <div className="mb-3 flex items-center gap-2 text-sm">
          {busy && <Loader2 size={14} className="animate-spin text-[var(--sl-muted)]" />}
          {error && <span className="text-red-600">{error}</span>}
        </div>
      )}

      <QueryState loading={loading} error={loadError} isEmpty={false} empty={null}>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
          <div className="overflow-hidden rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
            <div className="grid grid-cols-7 border-b border-[var(--sl-line)] text-center text-xs font-medium uppercase tracking-wide text-[var(--sl-muted)]">
              {WEEKDAYS.map((day) => (
                <div key={day} className="py-2">
                  {day}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7">
              {grid.map((day) => {
                const key = dayKey(day);
                const entries = byDay.get(key) ?? [];
                const inMonth = day.getMonth() === monthStart.getMonth();
                const isToday = key === dayKey(new Date());
                return (
                  <div
                    key={key}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setOverDay(key);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      drop(day);
                    }}
                    className={cn(
                      "min-h-[104px] border-b border-r border-[var(--sl-line)] p-1.5 transition",
                      !inMonth && "bg-slate-50/60 dark:bg-slate-950/40",
                      overDay === key && "bg-[var(--sl-soft)] dark:bg-primary-950/40",
                    )}
                  >
                    <span
                      className={cn(
                        "mb-1 inline-flex h-5 w-5 items-center justify-center rounded-full text-xs tabular-nums",
                        isToday
                          ? "bg-[var(--sl-action)] font-semibold text-white"
                          : inMonth
                            ? "text-[var(--sl-muted)]"
                            : "text-[var(--sl-muted)]",
                      )}
                    >
                      {day.getDate()}
                    </span>
                    <div className="space-y-1">
                      {entries.map((entry) => (
                        <EntryChip
                          key={`${entry.id}-${entry.kind}`}
                          entry={entry}
                          onDragStart={() => setDragging(entry)}
                          onDragEnd={() => setDragging(null)}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <aside>
            <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
              <CalendarClock size={13} /> Unscheduled
            </h2>
            {(data?.unscheduled ?? []).length === 0 ? (
              <p className="rounded-lg border border-dashed border-[var(--sl-line)] p-4 text-center text-xs text-[var(--sl-muted)]">
                Nothing waiting.
              </p>
            ) : (
              <div className="space-y-1.5">
                {(data?.unscheduled ?? []).map((entry) => (
                  <EntryChip
                    key={entry.id}
                    entry={entry}
                    onDragStart={() => setDragging(entry)}
                    onDragEnd={() => setDragging(null)}
                  />
                ))}
              </div>
            )}
            <p className="mt-3 text-xs text-[var(--sl-muted)]">
              Dragged here for the first time, an article is scheduled for{" "}
              {DEFAULT_HOUR}:00 on the day you drop it.
            </p>
          </aside>
        </div>
      </QueryState>
    </PageShell>
  );
}

function EntryChip({
  entry,
  onDragStart,
  onDragEnd,
}: {
  entry: CalendarEntry;
  onDragStart: () => void;
  onDragEnd: () => void;
}) {
  const time = entry.at
    ? new Date(entry.at).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";
  return (
    <Link
      href={`/studio/content/${encodeURIComponent(entry.slug)}`}
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      title={`${entry.title} — ${entry.kind.replace("_", " ")}`}
      className={cn(
        "block cursor-grab truncate rounded border px-1.5 py-1 text-[11px] leading-tight",
        KIND_STYLE[entry.kind] ?? KIND_STYLE.published,
      )}
    >
      {time && <span className="mr-1 opacity-60 tabular-nums">{time}</span>}
      {entry.title || "Untitled"}
    </Link>
  );
}

// -- date helpers -----------------------------------------------------------

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date: Date, count: number) {
  return new Date(date.getFullYear(), date.getMonth() + count, 1);
}

function addDays(date: Date, count: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + count);
  return next;
}

function dayKey(date: Date) {
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

/** Six Monday-first weeks covering `monthStart` — a fixed grid, so the layout
 *  does not reflow between a 4-row month and a 6-row one. */
function monthGrid(monthStart: Date) {
  const first = new Date(monthStart);
  const offset = (first.getDay() + 6) % 7; // Sunday = 0 in JS; we want Monday = 0
  const start = addDays(first, -offset);
  return Array.from({ length: 42 }, (_, index) => addDays(start, index));
}
