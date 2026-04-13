"use client";

import { useRef, useState } from "react";
import Modal from "@/components/ui/Modal";
import { normalizeMediaUrl } from "@/lib/media";
import { MediaChapter } from "@/lib/types";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function InteractiveAudioBlock({ data }: { data: Record<string, unknown> }) {
  const file = data.file as { url?: string } | undefined;
  const url = normalizeMediaUrl((data.url as string) || file?.url || "");
  const caption = (data.caption as string) || "";
  const chapters = (data.chapters as MediaChapter[]) || [];
  const [activeChapter, setActiveChapter] = useState<MediaChapter | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const handleChapterClick = (chapter: MediaChapter) => {
    if (audioRef.current) {
      audioRef.current.currentTime = chapter.time;
      audioRef.current.play().catch(() => {});
    }
    setActiveChapter(chapter);
  };

  return (
    <>
      <figure className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-6">
        <audio ref={audioRef} src={url} controls className="w-full" preload="metadata">
          Your browser does not support the audio element.
        </audio>

        {chapters.length > 0 && (
          <div className="mt-4 space-y-1">
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
          <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3">
            {caption}
          </figcaption>
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
