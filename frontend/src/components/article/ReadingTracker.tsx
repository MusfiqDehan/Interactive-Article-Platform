"use client";

import { useEffect, useRef } from "react";

import { track } from "@/lib/analytics";

/**
 * Records a view, a completed read, and outbound clicks.
 *
 * "Completed" is scroll depth plus dwell time, not scroll depth alone: a
 * reader who hits End immediately has reached the bottom without reading
 * anything, and counting that inflates the one metric editors use to judge
 * whether a piece held attention.
 *
 * Renders nothing. It sits inside the server-rendered article page as a small
 * client island, so the page itself stays a server component.
 */

const COMPLETE_AT_SCROLL = 0.85;
/** Below this, reaching the bottom is scrolling, not reading. */
const MIN_DWELL_MS = 20_000;

export function ReadingTracker({ articleId }: { articleId: number }) {
  // Stamped in the effect, not in `useRef(Date.now())`. Reading the clock
  // during render is impure -- React may render a component twice or discard
  // the result, so the "arrived at" time would not reliably be the time the
  // reader actually arrived.
  const mountedAt = useRef(0);
  const completed = useRef(false);

  useEffect(() => {
    mountedAt.current = Date.now();
    track("view", { article_id: articleId });

    const onScroll = () => {
      if (completed.current) return;
      const scrolled =
        (window.scrollY + window.innerHeight) /
        Math.max(document.documentElement.scrollHeight, 1);
      if (
        scrolled >= COMPLETE_AT_SCROLL &&
        Date.now() - mountedAt.current >= MIN_DWELL_MS
      ) {
        completed.current = true;
        track("read_complete", { article_id: articleId });
      }
    };

    const onClick = (event: MouseEvent) => {
      const anchor = (event.target as HTMLElement)?.closest?.("a");
      if (!anchor) return;
      const href = anchor.getAttribute("href") || "";
      if (!/^https?:\/\//.test(href)) return;
      if (href.startsWith(window.location.origin)) return;
      track("outbound_click", { article_id: articleId, target_id: href.slice(0, 100) });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("click", onClick);
    return () => {
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("click", onClick);
    };
  }, [articleId]);

  return null;
}
