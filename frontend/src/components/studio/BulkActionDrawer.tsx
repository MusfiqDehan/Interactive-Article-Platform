"use client";

import { AlertTriangle, Check, Loader2, X } from "lucide-react";
import { useState } from "react";

import { StatusBadge } from "@/components/studio/StatusBadge";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/primitives";
import { bulkDelete, bulkTransition, type BulkResult, type StudioArticleRow } from "@/lib/studio-api";

/**
 * Confirm-then-report drawer for bulk workflow actions.
 *
 * Two properties this exists to provide, both learned from how bulk actions
 * usually go wrong:
 *
 * 1. **Confirm shows exactly what will change** -- the articles by name, not a
 *    count. "Archive 23 articles?" is not something anyone can meaningfully
 *    agree to.
 * 2. **The result is per row.** Partial success is the normal outcome; a single
 *    "done" toast would hide the four that were refused, and the user would
 *    discover it days later.
 */

const ACTIONS = [
  { name: "publish", label: "Make public", destructive: false },
  { name: "submit", label: "Submit for review", destructive: false },
  { name: "approve", label: "Approve", destructive: false },
  { name: "unpublish", label: "Move to draft", destructive: true },
  { name: "archive", label: "Hide", destructive: true },
  { name: "delete", label: "Delete permanently", destructive: true },
] as const;

type Phase = "confirm" | "running" | "done";

export function BulkActionDrawer({
  open,
  onOpenChange,
  selected,
  onCompleted,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selected: StudioArticleRow[];
  onCompleted: () => void;
}) {
  const [action, setAction] = useState<string>("publish");
  const [phase, setPhase] = useState<Phase>("confirm");
  const [result, setResult] = useState<BulkResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ackDelete, setAckDelete] = useState(false);

  const chosen = ACTIONS.find((a) => a.name === action);
  const isDelete = action === "delete";
  const titleBySlug = new Map(selected.map((a) => [a.slug, a.title]));

  const reset = () => {
    setPhase("confirm");
    setResult(null);
    setError(null);
    setAckDelete(false);
  };

  const run = async () => {
    setPhase("running");
    setError(null);
    try {
      const slugs = selected.map((a) => a.slug);
      const outcome = isDelete
        ? await bulkDelete(slugs)
        : await bulkTransition(slugs, action);
      setResult(outcome);
      setPhase("done");
      onCompleted();
    } catch {
      setError("The request failed. Nothing was changed.");
      setPhase("confirm");
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent side="right" aria-describedby="bulk-desc">
        <DialogHeader>
          <DialogTitle>
            {phase === "done" ? "Results" : `${chosen?.label ?? "Action"} articles`}
          </DialogTitle>
          <DialogDescription id="bulk-desc">
            {phase === "done"
              ? `${result?.succeeded ?? 0} succeeded, ${result?.failed ?? 0} failed.`
              : `${selected.length} article${selected.length === 1 ? "" : "s"} selected.`}
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          {phase !== "done" && (
            <>
              <fieldset className="mb-5">
                <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
                  Action
                </legend>
                <div className="space-y-1">
                  {ACTIONS.map((option) => (
                    <label
                      key={option.name}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]"
                    >
                      <input
                        type="radio"
                        name="bulk-action"
                        value={option.name}
                        checked={action === option.name}
                        onChange={() => {
                          setAction(option.name);
                          setAckDelete(false);
                        }}
                      />
                      <span
                        className={
                          option.destructive
                            ? "text-red-600 dark:text-red-400"
                            : "text-[var(--sl-ink)]"
                        }
                      >
                        {option.label}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>

              {isDelete ? (
                <p className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-900 dark:bg-red-950/40 dark:text-red-200">
                  <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                  Permanently removes these articles, their revisions, and public
                  URLs. This cannot be undone. Use Hide if you only want them
                  off the site.
                </p>
              ) : (
                chosen?.destructive && (
                  <p className="mb-4 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                    <AlertTriangle size={15} className="mt-0.5 shrink-0" />
                    This takes content off the public site. Articles that are
                    already in another state are skipped rather than forced.
                  </p>
                )
              )}

              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
                Will be attempted
              </p>
              <ul className="divide-y divide-[var(--sl-line)] rounded-lg border border-[var(--sl-line)]">
                {selected.map((article) => (
                  <li
                    key={article.id}
                    className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                  >
                    <span className="truncate text-[var(--sl-ink)]">
                      {article.title || "Untitled"}
                    </span>
                    <StatusBadge status={article.status} />
                  </li>
                ))}
              </ul>

              {isDelete && (
                <label className="mt-4 flex cursor-pointer items-start gap-2 text-sm text-[var(--sl-ink)]">
                  <input
                    type="checkbox"
                    className="mt-0.5 rounded border-[var(--sl-line)]"
                    checked={ackDelete}
                    onChange={(event) => setAckDelete(event.target.checked)}
                  />
                  I understand these articles will be deleted completely and
                  cannot be recovered.
                </label>
              )}
            </>
          )}

          {phase === "done" && result && (
            <ul className="divide-y divide-[var(--sl-line)] rounded-lg border border-[var(--sl-line)]">
              {result.results.map((row) => (
                <li key={row.slug} className="flex items-start gap-2.5 px-3 py-2.5 text-sm">
                  {row.ok ? (
                    <Check size={15} className="mt-0.5 shrink-0 text-emerald-600" />
                  ) : (
                    <X size={15} className="mt-0.5 shrink-0 text-red-500" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[var(--sl-ink)]">
                      {titleBySlug.get(row.slug) || row.slug}
                    </span>
                    {row.ok && isDelete && (
                      <span className="block text-xs text-[var(--sl-muted)]">
                        Deleted
                      </span>
                    )}
                    {!row.ok && (
                      // The reason, not just the failure -- otherwise the only
                      // way to find out is to open each article and guess.
                      <span className="block text-xs text-red-600 dark:text-red-400">
                        {row.detail}
                      </span>
                    )}
                  </span>
                  {row.ok && row.status && <StatusBadge status={row.status} />}
                </li>
              ))}
            </ul>
          )}

          {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        </DialogBody>

        <DialogFooter>
          {phase === "done" ? (
            <Button onClick={() => onOpenChange(false)}>Close</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                variant={chosen?.destructive ? "destructive" : "default"}
                disabled={
                  phase === "running" ||
                  selected.length === 0 ||
                  (isDelete && !ackDelete)
                }
                onClick={run}
              >
                {phase === "running" && <Loader2 size={15} className="animate-spin" />}
                {chosen?.label} {selected.length}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
