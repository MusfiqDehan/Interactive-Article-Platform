"use client";

import { ArrowRight, Check, Loader2, MessageSquare, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageShell, QueryState } from "@/components/studio/PageShell";
import { StatusBadge } from "@/components/studio/StatusBadge";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { Button } from "@/components/ui/Button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/relative-time";
import {
  listReviewInbox,
  listReviews,
  resolveReview,
  runTransition,
  type StudioArticleRow,
} from "@/lib/studio-api";

/**
 * Two-pane review inbox.
 *
 * The list on the left is the queue; the right pane is where the decision is
 * made. Approving is the one action that must not require opening the article
 * in another tab and losing your place in the queue — reviewing twenty drafts
 * is a rhythm, and every context switch breaks it.
 */

const SCOPES = [
  { value: "queue", label: "Awaiting review" },
  { value: "mine", label: "Assigned to me" },
  { value: "requested", label: "I requested" },
] as const;

type Scope = (typeof SCOPES)[number]["value"];

export default function ReviewPage() {
  const [scope, setScope] = useState<Scope>("queue");
  const [openId, setOpenId] = useState<number | null>(null);

  const { data, loading, error, refresh } = useStudioQuery(async () => {
    if (scope === "queue") return (await listReviewInbox()).results;
    const assignments = (await listReviews(scope)).results;
    return assignments;
  }, [scope]);

  const rows = data ?? [];

  return (
    <PageShell
      title="Review"
      description="Drafts submitted for review, and the assignments you are part of."
    >
      <Tabs value={scope} onValueChange={(value) => setScope(value as Scope)}>
        <TabsList>
          {SCOPES.map((option) => (
            <TabsTrigger key={option.value} value={option.value}>
              {option.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="mt-5">
        <QueryState
          loading={loading}
          error={error}
          isEmpty={rows.length === 0}
          empty={
            scope === "queue"
              ? "Nothing is waiting for review. "
              : "No assignments in this view."
          }
        >
          {scope === "queue" ? (
            <div className="grid gap-5 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
              <ul className="divide-y divide-[var(--sl-line)] overflow-hidden rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
                {(rows as StudioArticleRow[]).map((article) => (
                  <li key={article.id}>
                    <button
                      onClick={() => setOpenId(article.id)}
                      className={cn(
                        "flex w-full flex-col items-start gap-1 px-4 py-3 text-left transition",
                        openId === article.id
                          ? "bg-[var(--sl-soft)] dark:bg-primary-950/40"
                          : "hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]",
                      )}
                    >
                      <span className="w-full truncate text-sm font-medium text-[var(--sl-ink)]">
                        {article.title || "Untitled"}
                      </span>
                      <span className="flex items-center gap-2 text-xs text-[var(--sl-muted)]">
                        <StatusBadge status={article.status} />
                        {article.author?.name ?? "Unknown"} ·{" "}
                        {relativeTime(article.updated_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>

              <ReviewDetail
                article={(rows as StudioArticleRow[]).find((a) => a.id === openId) ?? null}
                onDone={() => {
                  setOpenId(null);
                  refresh();
                }}
              />
            </div>
          ) : (
            <AssignmentList
              assignments={rows as Awaited<ReturnType<typeof listReviews>>["results"]}
              onDone={refresh}
            />
          )}
        </QueryState>
      </div>
    </PageShell>
  );
}

function ReviewDetail({
  article,
  onDone,
}: {
  article: StudioArticleRow | null;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!article) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-dashed border-[var(--sl-line)] p-10 text-sm text-[var(--sl-muted)]">
        Pick a draft to review.
      </div>
    );
  }

  const act = async (transition: string) => {
    setBusy(transition);
    setError(null);
    try {
      await runTransition(article.slug, transition);
      onDone();
    } catch (err: unknown) {
      const response = (err as { response?: { data?: { detail?: string } } }).response;
      setError(response?.data?.detail ?? "That action was refused.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-display text-lg font-bold text-[var(--sl-ink)]">
            {article.title || "Untitled"}
          </h2>
          <p className="mt-0.5 text-sm text-[var(--sl-muted)]">
            {article.author?.name ?? "Unknown"} · {article.word_count} words ·{" "}
            {article.reading_time} min read
          </p>
        </div>
        <Button size="sm" variant="secondary" asChild>
          <Link href={`/studio/content/${encodeURIComponent(article.slug)}`}>
            Open <ArrowRight size={13} />
          </Link>
        </Button>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <div className="mt-5 flex flex-wrap gap-2 border-t border-[var(--sl-line)] pt-4">
        <Button size="sm" onClick={() => act("approve")} disabled={Boolean(busy)}>
          {busy === "approve" ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Check size={14} />
          )}
          Approve
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => act("request_changes")}
          disabled={Boolean(busy)}
        >
          {busy === "request_changes" ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <X size={14} />
          )}
          Request changes
        </Button>
        <Button size="sm" variant="ghost" asChild>
          <Link href={`/studio/content/${encodeURIComponent(article.slug)}#comments`}>
            <MessageSquare size={14} /> Comment
          </Link>
        </Button>
      </div>
    </div>
  );
}

function AssignmentList({
  assignments,
  onDone,
}: {
  assignments: Awaited<ReturnType<typeof listReviews>>["results"];
  onDone: () => void;
}) {
  const [busy, setBusy] = useState<number | null>(null);

  const resolve = async (id: number, state: string) => {
    setBusy(id);
    try {
      await resolveReview(id, state);
      onDone();
    } finally {
      setBusy(null);
    }
  };

  return (
    <ul className="divide-y divide-[var(--sl-line)] rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
      {assignments.map((assignment) => (
        <li key={assignment.id} className="flex items-center gap-3 px-4 py-3">
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-[var(--sl-ink)]">
              {assignment.article_title ?? `Article #${assignment.article}`}
            </span>
            <span className="block text-xs text-[var(--sl-muted)]">
              {assignment.state === "pending"
                ? `Requested ${relativeTime(assignment.created_at)}`
                : `${assignment.state.replace("_", " ")} ${relativeTime(assignment.resolved_at ?? assignment.created_at)}`}
              {assignment.note && ` — ${assignment.note}`}
            </span>
          </span>
          {assignment.state === "pending" && (
            <span className="flex shrink-0 gap-1.5">
              <Button
                size="sm"
                onClick={() => resolve(assignment.id, "approved")}
                disabled={busy === assignment.id}
              >
                Approve
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => resolve(assignment.id, "changes_requested")}
                disabled={busy === assignment.id}
              >
                Changes
              </Button>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

