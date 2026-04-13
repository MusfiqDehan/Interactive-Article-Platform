"use client";

import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { MediaChapter } from "@/lib/types";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function extractVideoId(source: string): string {
  try {
    if (source.includes("youtube.com/watch")) {
      return new URL(source).searchParams.get("v") || "";
    } else if (source.includes("youtu.be/")) {
      return source.split("youtu.be/")[1]?.split("?")[0] || "";
    } else if (source.includes("youtube.com/embed/")) {
      return source.split("embed/")[1]?.split("?")[0] || "";
    }
  } catch {
    // ignore URL parse errors
  }
  return "";
}

export default function InteractiveYouTubeBlock({ data }: { data: Record<string, unknown> }) {
  const source = (data.source as string) || (data.url as string) || (data.embed as string) || "";
  const caption = (data.caption as string) || "";
  const chapters = (data.chapters as MediaChapter[]) || [];
  const videoId = extractVideoId(source);

  const [startTime, setStartTime] = useState(0);
  const [activeChapter, setActiveChapter] = useState<MediaChapter | null>(null);

  const embedUrl = videoId
    ? `https://www.youtube-nocookie.com/embed/${videoId}?start=${startTime}${startTime > 0 ? "&autoplay=1" : ""}`
    : source;

  if (!embedUrl) return null;

  const handleChapterClick = (chapter: MediaChapter) => {
    setStartTime(chapter.time);
    setActiveChapter(chapter);
  };

  return (
    <>
      <figure>
        <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-slate-900">
          <iframe
            key={startTime}
            src={embedUrl}
            title={caption || "YouTube Video"}
            className="absolute inset-0 w-full h-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            loading="lazy"
          />
        </div>

        {chapters.length > 0 && (
          <div className="mt-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 space-y-1">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
              Chapters
            </p>
            {chapters.map((chapter) => (
              <button
                key={chapter.id}
                onClick={() => handleChapterClick(chapter)}
                className="flex items-center gap-3 w-full text-left px-3 py-2 rounded-lg hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors group"
              >
                <span className="text-xs font-mono text-primary-600 dark:text-primary-400 min-w-[3rem]">
                  {formatTime(chapter.time)}
                </span>
                <span className="text-sm text-slate-700 dark:text-slate-300 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">
                  {chapter.label}
                </span>
                <span className="ml-auto text-slate-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity">
                  Click for details
                </span>
              </button>
            ))}
          </div>
        )}

        {caption && (
          <figcaption
            className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3"
            dangerouslySetInnerHTML={{ __html: caption }}
          />
        )}
      </figure>

      <Modal
        isOpen={!!activeChapter}
        onClose={() => setActiveChapter(null)}
        title={activeChapter?.modal_title || "Chapter Details"}
        size="lg"
      >
        <div
          className="prose prose-slate dark:prose-invert max-w-none"
          dangerouslySetInnerHTML={{ __html: activeChapter?.modal_content || "" }}
        />
      </Modal>
    </>
  );
}
