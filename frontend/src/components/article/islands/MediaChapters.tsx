"use client";

import { useRef } from "react";

import { useAnnotations } from "../annotations/AnnotationProvider";

/**
 * Media element plus a chapter list that seeks it.
 *
 * The chapter list is a real `<ol>` of buttons, so the labels and timestamps
 * are in the HTML regardless of JS; clicking only adds the seek behaviour.
 */

interface Chapter {
  id: string;
  time: number;
  label?: string;
  modal_title?: string;
}

export function MediaChapters({
  kind,
  src,
  chapters,
}: {
  kind: "audio" | "video";
  src: string;
  chapters: Chapter[];
}) {
  const ref = useRef<HTMLMediaElement | null>(null);
  const { open, has } = useAnnotations();

  const jump = (chapter: Chapter) => {
    const el = ref.current;
    if (el) {
      el.currentTime = chapter.time || 0;
      void el.play().catch(() => {
        /* autoplay may be blocked; seeking still worked */
      });
    }
    if (chapter.id && has(chapter.id)) open(chapter.id);
  };

  return (
    <div className="space-y-3">
      {kind === "audio" ? (
        <audio
          ref={ref as React.RefObject<HTMLAudioElement>}
          controls
          preload="metadata"
          className="w-full"
        >
          <source src={src} />
        </audio>
      ) : (
        <video
          ref={ref as React.RefObject<HTMLVideoElement>}
          controls
          preload="metadata"
          className="w-full rounded-xl"
        >
          <source src={src} />
        </video>
      )}

      <ol className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 dark:divide-slate-700 dark:border-slate-700">
        {chapters.map((chapter) => (
          <li key={chapter.id || chapter.time}>
            <button
              type="button"
              onClick={() => jump(chapter)}
              className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              <time className="font-mono text-xs text-primary-600 dark:text-primary-400">
                {formatTime(chapter.time)}
              </time>
              <span className="text-slate-700 dark:text-slate-200">
                {chapter.label || chapter.modal_title || "Chapter"}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds || 0));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}
