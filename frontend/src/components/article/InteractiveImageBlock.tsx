"use client";

import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { ImageHotspot } from "@/lib/types";

/* eslint-disable @next/next/no-img-element */
export default function InteractiveImageBlock({ data }: { data: Record<string, unknown> }) {
  const file = data.file as { url?: string } | undefined;
  const url = (data.url as string) || file?.url || "";
  const caption = (data.caption as string) || "";
  const hotspots = (data.hotspots as ImageHotspot[]) || [];
  const [activeHotspot, setActiveHotspot] = useState<ImageHotspot | null>(null);

  return (
    <>
      <figure className="relative max-w-3xl mx-auto">
        <div className="relative group">
          <img
            src={url}
            alt={caption || "Interactive image"}
            className="w-full rounded-xl"
            loading="lazy"
          />

          {/* Hotspot overlays */}
          {hotspots.map((hotspot) => (
            <button
              key={hotspot.id}
              onClick={() => setActiveHotspot(hotspot)}
              className={`absolute border-2 border-primary-500 bg-primary-500/20 hover:bg-primary-500/40 transition-all cursor-pointer group/hotspot ${
                hotspot.shape === "circle" ? "rounded-full" : "rounded-lg"
              }`}
              style={{
                left: `${hotspot.x}%`,
                top: `${hotspot.y}%`,
                width: `${hotspot.width}%`,
                height: `${hotspot.height}%`,
              }}
              title={hotspot.modal_title || "Click for details"}
            >
              <span className="absolute inset-0 flex items-center justify-center">
                <span className="w-6 h-6 bg-primary-500 rounded-full flex items-center justify-center shadow-lg animate-pulse">
                  <span className="text-white text-xs font-bold">+</span>
                </span>
              </span>
            </button>
          ))}

          {hotspots.length > 0 && (
            <div className="absolute bottom-3 right-3 bg-black/60 text-white text-xs px-3 py-1.5 rounded-full backdrop-blur-sm">
              Click hotspots for details
            </div>
          )}
        </div>

        {caption && (
          <figcaption
            className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3"
            dangerouslySetInnerHTML={{ __html: caption }}
          />
        )}
      </figure>

      <Modal
        isOpen={!!activeHotspot}
        onClose={() => setActiveHotspot(null)}
        title={activeHotspot?.modal_title || "Details"}
        size="lg"
      >
        <div
          className="prose prose-slate dark:prose-invert max-w-none"
          dangerouslySetInnerHTML={{ __html: activeHotspot?.modal_content || "" }}
        />
      </Modal>
    </>
  );
}
