"use client";

import { useMemo, useRef, useState, useSyncExternalStore } from "react";

/**
 * Google-style result preview, truncated by **pixel width** rather than
 * character count.
 *
 * Character counts are the usual approach and they are wrong: Google truncates
 * at roughly 600px (desktop) / 680px (mobile) of rendered text, and glyph
 * widths vary enormously. "IIIIIIIIIIIIIIIIIIII" and "WWWWWWWWWWWWWWWWWWWW" are
 * both twenty characters and nowhere near the same width. That gap matters most
 * for the Bengali content this platform serves, where a "60 character" title
 * can render far wider than a Latin one and get cut mid-word in the SERP while
 * the editor's counter still shows green.
 *
 * Measurement uses a canvas rather than a hidden DOM node so it costs no layout
 * and can run on every keystroke.
 */

const TITLE_FONT = "20px Arial, sans-serif";
const DESC_FONT = "14px Arial, sans-serif";
const LIMITS = {
  desktop: { title: 600, description: 990 },
  mobile: { title: 680, description: 1000 },
} as const;

type Device = keyof typeof LIMITS;

/** Server/client difference only -- the value never changes after mount. */
const subscribeNever = () => () => {};

function useTextMeasurer() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  return useMemo(() => {
    return (text: string, font: string): number => {
      if (typeof document === "undefined") return 0;
      if (!canvasRef.current) canvasRef.current = document.createElement("canvas");
      const context = canvasRef.current.getContext("2d");
      if (!context) return 0;
      context.font = font;
      return context.measureText(text).width;
    };
  }, []);
}

/** Trim to `maxWidth`, cutting on a word boundary and appending an ellipsis. */
function truncateToWidth(
  text: string,
  font: string,
  maxWidth: number,
  measure: (t: string, f: string) => number,
): { text: string; truncated: boolean; width: number } {
  const width = measure(text, font);
  if (width <= maxWidth || !text) return { text, truncated: false, width };

  let low = 0;
  let high = text.length;
  while (low < high) {
    const mid = Math.ceil((low + high) / 2);
    if (measure(`${text.slice(0, mid)} …`, font) <= maxWidth) low = mid;
    else high = mid - 1;
  }
  const cut = text.slice(0, low);
  // Prefer a word boundary; Google does not cut mid-word.
  const lastSpace = cut.lastIndexOf(" ");
  const clean = lastSpace > cut.length * 0.6 ? cut.slice(0, lastSpace) : cut;
  return { text: `${clean} …`, truncated: true, width };
}

export function SnippetPreview({
  title,
  description,
  url,
}: {
  title: string;
  description: string;
  url: string;
}) {
  const measure = useTextMeasurer();
  const [device, setDevice] = useState<Device>("desktop");
  // Canvas measurement is unavailable during SSR, so the first paint would
  // differ from the client's. Rendering untruncated until mounted keeps
  // hydration consistent and is visibly correct for short values.
  const mounted = useSyncExternalStore(
    subscribeNever,
    () => true, // client
    () => false, // server + hydration
  );

  const limits = LIMITS[device];
  const shownTitle = mounted
    ? truncateToWidth(title, TITLE_FONT, limits.title, measure)
    : { text: title, truncated: false, width: 0 };
  const shownDescription = mounted
    ? truncateToWidth(description, DESC_FONT, limits.description, measure)
    : { text: description, truncated: false, width: 0 };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
          Search preview
        </span>
        <div className="flex rounded-md border border-[var(--sl-line)] p-0.5 text-xs">
          {(["desktop", "mobile"] as Device[]).map((option) => (
            <button
              key={option}
              onClick={() => setDevice(option)}
              className={`rounded px-2 py-0.5 capitalize transition ${
                device === option
                  ? "bg-[var(--sl-card)] text-white bg-[var(--sl-action)] text-[var(--sl-ink)]"
                  : "text-[var(--sl-muted)]"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <div
        className="rounded-lg border border-[var(--sl-line)] bg-[var(--sl-card)] p-3"
        style={{ maxWidth: device === "desktop" ? 600 : 400 }}
      >
        <p className="truncate text-xs text-[var(--sl-ink)]">{url}</p>
        <p className="mt-0.5 text-[18px] leading-snug text-[#1a0dab] dark:text-[#8ab4f8]">
          {shownTitle.text || "Untitled"}
        </p>
        <p className="mt-1 text-[13px] leading-snug text-[var(--sl-ink)]">
          {shownDescription.text || (
            <span className="italic text-[var(--sl-muted)]">
              No meta description — Google will pick text from the page.
            </span>
          )}
        </p>
      </div>

      {mounted && (
        <dl className="mt-2 space-y-1 text-xs">
          <WidthMeter
            label="Title"
            width={shownTitle.width}
            limit={limits.title}
            truncated={shownTitle.truncated}
          />
          <WidthMeter
            label="Description"
            width={shownDescription.width}
            limit={limits.description}
            truncated={shownDescription.truncated}
          />
        </dl>
      )}
    </div>
  );
}

function WidthMeter({
  label,
  width,
  limit,
  truncated,
}: {
  label: string;
  width: number;
  limit: number;
  truncated: boolean;
}) {
  const pct = Math.min(100, Math.round((width / limit) * 100));
  return (
    <div className="flex items-center gap-2">
      <dt className="w-20 shrink-0 text-[var(--sl-muted)]">{label}</dt>
      <dd className="flex flex-1 items-center gap-2">
        <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--sl-soft)]">
          <span
            className={`block h-full rounded-full transition-all ${
              truncated ? "bg-red-500" : pct > 85 ? "bg-amber-500" : "bg-emerald-500"
            }`}
            style={{ width: `${pct}%` }}
          />
        </span>
        <span
          className={`w-24 shrink-0 text-right tabular-nums ${
            truncated ? "text-red-600" : "text-[var(--sl-muted)]"
          }`}
        >
          {Math.round(width)}/{limit}px
        </span>
      </dd>
    </div>
  );
}
