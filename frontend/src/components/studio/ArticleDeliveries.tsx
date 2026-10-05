"use client";

import Link from "next/link";

import { DeliveryList } from "@/components/studio/DeliveryList";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { listDeliveries } from "@/lib/studio-api";

/**
 * This article's outbound deliveries, inside the editor.
 *
 * The same list as the global log, filtered. It belongs here because the
 * question an author asks is "did *this* piece reach the partner site?", and
 * answering it from a site-wide log means scanning for a title among everything
 * published that day.
 */
export function ArticleDeliveries({ articleId }: { articleId: number }) {
  const { data, loading, error, refresh } = useStudioQuery(
    () => listDeliveries({ article: articleId, page_size: 10 }),
    [articleId],
  );
  const rows = data?.results ?? [];

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
          Deliveries
        </span>
        <Link
          href="/studio/distribution"
          className="text-xs text-[var(--sl-accent)] hover:underline"
        >
          All destinations
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--sl-muted)]">Loading…</p>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-[var(--sl-line)] p-3 text-xs text-[var(--sl-muted)]">
          Nothing sent yet. Publishing fans this article out to every active
          destination.
        </p>
      ) : (
        <DeliveryList deliveries={rows} onChanged={refresh} />
      )}
    </div>
  );
}
