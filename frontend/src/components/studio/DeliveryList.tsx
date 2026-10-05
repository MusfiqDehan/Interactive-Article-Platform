"use client";

import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  RotateCw,
  SkipForward,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { Badge, type BadgeTone } from "@/components/ui/primitives";
import { Button } from "@/components/ui/Button";
import { relativeTime } from "@/lib/relative-time";
import { retryDelivery, type Delivery, type DeliveryState } from "@/lib/studio-api";

/**
 * The delivery log, with the payload and the response behind a disclosure.
 *
 * A row that only says "failed" is unactionable. What an operator needs is the
 * exact body we sent and the exact body that came back, which is why both are
 * stored on the delivery and shown here rather than left in a server log
 * nobody has access to.
 */

const STATE: Record<
  DeliveryState,
  { label: string; tone: BadgeTone; Icon: typeof Check }
> = {
  pending: { label: "Queued", tone: "slate", Icon: Clock },
  delivering: { label: "Sending", tone: "blue", Icon: Loader2 },
  delivered: { label: "Delivered", tone: "green", Icon: Check },
  failed: { label: "Retrying", tone: "amber", Icon: AlertCircle },
  abandoned: { label: "Gave up", tone: "red", Icon: XCircle },
  skipped: { label: "Skipped", tone: "slate", Icon: SkipForward },
};

export function DeliveryList({
  deliveries,
  onChanged,
}: {
  deliveries: Delivery[];
  onChanged: () => void;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<{ id: number; message: string } | null>(null);

  const retry = async (delivery: Delivery) => {
    setBusy(delivery.id);
    setError(null);
    try {
      await retryDelivery(delivery.id);
      onChanged();
    } catch (err: unknown) {
      const response = (err as { response?: { data?: { detail?: string } } }).response;
      setError({
        id: delivery.id,
        message: response?.data?.detail ?? "The retry could not be started.",
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <ul className="divide-y divide-[var(--sl-line)] rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
      {deliveries.map((delivery) => {
        const state = STATE[delivery.state] ?? STATE.pending;
        const expanded = open === delivery.id;
        return (
          <li key={delivery.id}>
            <div className="flex flex-wrap items-center gap-3 px-4 py-3">
              <button
                onClick={() => setOpen(expanded ? null : delivery.id)}
                aria-expanded={expanded}
                className="shrink-0 hover:text-[var(--sl-ink)]"
              >
                {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </button>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-[var(--sl-ink)]">
                  {delivery.article_label || "Untitled"}
                </span>
                <span className="block truncate text-xs text-[var(--sl-muted)]">
                  {delivery.event} → {delivery.destination_name} ·{" "}
                  {relativeTime(delivery.delivered_at ?? delivery.created_at)}
                </span>
              </span>

              {delivery.attempts > 1 && (
                <span className="shrink-0 text-xs tabular-nums text-[var(--sl-muted)]">
                  {delivery.attempts} attempts
                </span>
              )}
              {delivery.state === "failed" && delivery.next_attempt_at && (
                // Not "failed" alone: it is going to be retried automatically,
                // and saying when stops anyone re-triggering it by hand.
                <span className="shrink-0 text-xs text-amber-600">
                  next try {relativeTime(delivery.next_attempt_at)}
                </span>
              )}

              <Badge tone={state.tone}>
                <state.Icon
                  size={11}
                  className={delivery.state === "delivering" ? "animate-spin" : ""}
                />
                {state.label}
              </Badge>

              {delivery.state !== "delivered" && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy === delivery.id}
                  onClick={() => retry(delivery)}
                >
                  {busy === delivery.id ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <RotateCw size={13} />
                  )}
                  Retry now
                </Button>
              )}
            </div>

            {error?.id === delivery.id && (
              <p className="px-4 pb-2 text-xs text-red-600">{error.message}</p>
            )}

            {expanded && (
              <div className="space-y-3 border-t border-[var(--sl-line)] bg-[var(--sl-soft)] px-4 py-3 bg-[var(--sl-card)]">
                {delivery.last_error && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-500">
                      Error
                    </p>
                    <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded bg-red-50 p-2 text-xs text-red-800 dark:bg-red-950/40 dark:text-red-300">
                      {delivery.last_error}
                    </pre>
                  </div>
                )}
                <Snippet label="Sent" value={delivery.payload_snapshot} />
                <Snippet
                  label={`Received${delivery.response_status ? ` (HTTP ${delivery.response_status})` : ""}`}
                  value={delivery.response_snapshot}
                />
                <p className="text-xs text-[var(--sl-muted)]">
                  Event id <code>{delivery.event_id}</code> — the receiver can use
                  this to dedupe if it gets the same delivery twice.
                </p>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Snippet({ label, value }: { label: string; value: Record<string, unknown> }) {
  const text = JSON.stringify(value ?? {}, null, 2);
  if (text === "{}") return null;
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
        {label}
      </p>
      {/* Its own scroll container: a long payload must not make the whole
          page scroll sideways. */}
      <pre className="max-h-56 overflow-auto rounded bg-[var(--sl-card)] p-2 text-xs text-[var(--sl-ink)]">
        {text}
      </pre>
    </div>
  );
}
