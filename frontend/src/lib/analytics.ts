"use client";

/**
 * The reader-side event beacon.
 *
 * Three properties, in priority order:
 *
 * 1. **It never blocks the page.** Events are queued in memory and flushed
 *    with `navigator.sendBeacon`, which the browser sends outside the page's
 *    lifetime — so a flush during navigation completes instead of being
 *    cancelled, and nothing waits on the network.
 * 2. **It never throws.** Analytics failing must not surface as a console
 *    error on an article page, so every path swallows.
 * 3. **It batches.** One request per page rather than one per interaction:
 *    an article with fifteen annotations would otherwise make fifteen
 *    requests, mostly while the reader is still reading.
 */

import { publicEnvFromWindow } from "./runtime-config";

export type EventName =
  | "view"
  | "read_complete"
  | "annotation_open"
  | "hotspot_open"
  | "media_play"
  | "chapter_jump"
  | "outbound_click"
  | "share"
  | "search";

interface QueuedEvent {
  name: EventName;
  article_id?: number;
  target_id?: string;
  path?: string;
  referrer?: string;
  locale?: string;
  metadata?: Record<string, unknown>;
}

const queue: QueuedEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let listenersAttached = false;

/** Matches the server's per-request cap, so nothing is silently dropped. */
const MAX_BATCH = 50;
const FLUSH_AFTER_MS = 4000;

function endpoint(): string | null {
  const base = publicEnvFromWindow()?.apiBase || process.env.NEXT_PUBLIC_API_BASE_URL;
  const key = publicEnvFromWindow()?.eventsApiKey;
  if (!base || !key) return null;
  return `${base.replace(/\/$/, "")}/v1/public/events/`;
}

export function flush(): void {
  if (typeof window === "undefined" || queue.length === 0) return;
  const url = endpoint();
  if (!url) {
    queue.length = 0;
    return;
  }

  const batch = queue.splice(0, MAX_BATCH);
  const body = JSON.stringify({ events: batch });

  try {
    // sendBeacon cannot set headers, so the API key rides in the query string.
    // It is a read/write-events key scoped to one site and already public in
    // the page's own requests — there is nothing here a page source view does
    // not already reveal.
    const key = publicEnvFromWindow()?.eventsApiKey ?? "";
    const target = `${url}?api_key=${encodeURIComponent(key)}`;

    if (navigator.sendBeacon) {
      navigator.sendBeacon(target, new Blob([body], { type: "application/json" }));
      return;
    }
    // keepalive so a flush started during navigation still completes.
    void fetch(target, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* analytics must never surface on a reader's page */
  }
}

function scheduleFlush() {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flush();
  }, FLUSH_AFTER_MS);
}

function attachListeners() {
  if (listenersAttached || typeof document === "undefined") return;
  listenersAttached = true;
  // `visibilitychange`, not `unload`: mobile browsers frequently never fire
  // unload, so a reader who switches apps mid-article would lose the batch.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", flush);
}

export function track(name: EventName, payload: Omit<QueuedEvent, "name"> = {}): void {
  if (typeof window === "undefined") return;
  attachListeners();
  queue.push({
    name,
    path: window.location.pathname,
    referrer: document.referrer || "",
    locale: document.documentElement.lang || "",
    ...payload,
  });
  if (queue.length >= MAX_BATCH) flush();
  else scheduleFlush();
}
