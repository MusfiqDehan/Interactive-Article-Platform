"use client";

import { useState } from "react";

import { useAnnotations } from "../annotations/AnnotationProvider";

/**
 * YouTube facade: a static thumbnail until the reader clicks.
 *
 * A bare iframe costs roughly half a megabyte of third-party JS on load, on
 * every article that embeds a video. The facade defers all of it and keeps the
 * link crawlable in the meantime.
 */

interface Chapter {
  id: string;
  time: number;
  label?: string;
  modal_title?: string;
}

export function YouTubeEmbed({
  source,
  caption,
  chapters,
}: {
  source: string;
  caption?: string;
  chapters?: Chapter[];
}) {
  const videoId = extractId(source);
  const [startAt, setStartAt] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const { open, has } = useAnnotations();

  if (!videoId) return null;

  const jump = (chapter: Chapter) => {
    setStartAt(chapter.time || 0);
    setPlaying(true);
    if (chapter.id && has(chapter.id)) open(chapter.id);
  };

  return (
    <figure className="not-prose space-y-3">
      <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-slate-900">
        {playing ? (
          <iframe
            // Remounting on startAt is what makes the chapter seek take effect;
            // the embed has no imperative seek API from the parent frame.
            key={startAt ?? "start"}
            src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1${
              startAt ? `&start=${Math.floor(startAt)}` : ""
            }`}
            title={caption || "Embedded video"}
            className="absolute inset-0 h-full w-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture"
            allowFullScreen
          />
        ) : (
          <button
            type="button"
            onClick={() => setPlaying(true)}
            className="group absolute inset-0 h-full w-full"
            aria-label="Play video"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`}
              alt={caption || "Video thumbnail"}
              className="h-full w-full object-cover"
              loading="lazy"
            />
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 text-white shadow-lg transition group-hover:scale-110">
                <svg viewBox="0 0 24 24" fill="currentColor" className="ml-1 h-7 w-7">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </span>
            </span>
          </button>
        )}
      </div>

      {chapters && chapters.length > 0 && (
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
      )}

      {caption ? (
        <figcaption
          className="text-center text-sm text-slate-500"
          dangerouslySetInnerHTML={{ __html: caption }}
        />
      ) : null}
    </figure>
  );
}

function extractId(source: string): string {
  if (!source) return "";
  const watch = source.match(/[?&]v=([^&]+)/);
  const short = source.match(/youtu\.be\/([^?&/]+)/);
  const embed = source.match(/\/embed\/([^?&/]+)/);
  return watch?.[1] || short?.[1] || embed?.[1] || (/^[\w-]{11}$/.test(source) ? source : "");
}

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}
