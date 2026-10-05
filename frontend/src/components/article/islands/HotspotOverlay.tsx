"use client";

import { useAnnotations } from "../annotations/AnnotationProvider";

/**
 * Clickable hotspots layered over a server-rendered image.
 *
 * The image itself stays server HTML; only this positioning layer hydrates.
 * Hotspot bodies live in the annotation appendix, so their text is in the page
 * even for a reader who never clicks.
 */

interface Hotspot {
  id: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  shape?: "circle" | "rect";
  modal_title?: string;
}

export function HotspotOverlay({ hotspots }: { hotspots: Hotspot[] }) {
  const { open, has } = useAnnotations();
  const usable = hotspots.filter((h) => h?.id);
  if (usable.length === 0) return null;

  return (
    <>
      <div className="pointer-events-none absolute inset-0">
        {usable.map((hotspot) => (
          <button
            key={hotspot.id}
            type="button"
            onClick={() => has(hotspot.id) && open(hotspot.id)}
            aria-label={hotspot.modal_title || "Show details"}
            aria-haspopup="dialog"
            className="pointer-events-auto absolute flex items-center justify-center border-2 border-white/90 bg-primary-500/30 text-white shadow-lg backdrop-blur-[1px] transition hover:bg-primary-500/50 focus:outline-none focus:ring-2 focus:ring-white"
            style={{
              left: `${hotspot.x}%`,
              top: `${hotspot.y}%`,
              width: `${hotspot.width ?? 8}%`,
              height: `${hotspot.height ?? 8}%`,
              borderRadius: hotspot.shape === "rect" ? "0.375rem" : "9999px",
            }}
          >
            <span className="text-lg font-bold leading-none">+</span>
          </button>
        ))}
      </div>
      <span className="absolute bottom-2 right-2 rounded-full bg-black/60 px-2 py-1 text-xs text-white">
        {usable.length} hotspot{usable.length === 1 ? "" : "s"}
      </span>
    </>
  );
}
