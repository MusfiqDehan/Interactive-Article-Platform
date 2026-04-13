"use client";

import { useState, useMemo } from "react";
import Modal from "@/components/ui/Modal";
import { normalizeMediaUrl } from "@/lib/media";
import { InteractiveAnnotation } from "@/lib/types";

// ─── HTML parser ──────────────────────────────────────────────────────────────

type Segment =
  | { kind: "text"; html: string }
  | { kind: "annotation"; id: string; innerText: string };

function parseAnnotatedHTML(html: string): Segment[] {
  const segments: Segment[] = [];
  // Match <span ... data-annotation-id="ID" ...>CONTENT</span>
  const regex =
    /<span[^>]*?data-annotation-id="([^"]+)"[^>]*?>([\s\S]*?)<\/span>/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(html)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: "text", html: html.slice(lastIndex, match.index) });
    }
    // Strip any editor-only icon spans from the inner text
    const innerText = match[2]
      .replace(/<span[^>]*?data-annotation-icon[^>]*?>[\s\S]*?<\/span>/g, "")
      .trim();
    segments.push({ kind: "annotation", id: match[1], innerText });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < html.length) {
    segments.push({ kind: "text", html: html.slice(lastIndex) });
  }

  return segments;
}

// ─── Modal content ────────────────────────────────────────────────────────────

function YouTubeEmbed({ source }: { source: string }) {
  let embedUrl = source;
  try {
    if (source.includes("youtube.com/watch")) {
      embedUrl = `https://www.youtube-nocookie.com/embed/${new URL(source).searchParams.get("v") || ""}`;
    } else if (source.includes("youtu.be/")) {
      embedUrl = `https://www.youtube-nocookie.com/embed/${source.split("youtu.be/")[1]?.split("?")[0] || ""}`;
    }
  } catch { /* ignore */ }

  return (
    <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-slate-900">
      <iframe
        src={embedUrl}
        title="YouTube video"
        className="absolute inset-0 w-full h-full"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        loading="lazy"
      />
    </div>
  );
}

function AnnotationModalContent({
  annotation,
}: {
  annotation: InteractiveAnnotation;
}) {
  switch (annotation.type) {
    case "text":
      return (
        <div
          className="prose prose-slate dark:prose-invert max-w-none"
          dangerouslySetInnerHTML={{ __html: annotation.modal_content || "" }}
        />
      );

    case "image":
      return (
        /* eslint-disable @next/next/no-img-element */
        <figure className="m-0">
          <img
            src={normalizeMediaUrl(annotation.image_url)}
            alt={annotation.modal_title}
            className="w-full rounded-xl"
          />
          {annotation.image_caption && (
            <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3">
              {annotation.image_caption}
            </figcaption>
          )}
        </figure>
      );

    case "audio":
      return (
        <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4">
          <audio
            src={normalizeMediaUrl(annotation.audio_url)}
            controls
            className="w-full"
            preload="metadata"
          >
            Your browser does not support the audio element.
          </audio>
        </div>
      );

    case "video":
      return (
        <div className="rounded-xl overflow-hidden bg-slate-900">
          <video
            src={normalizeMediaUrl(annotation.video_url)}
            controls
            className="w-full"
            preload="metadata"
          >
            Your browser does not support the video element.
          </video>
        </div>
      );

    case "youtube":
      return <YouTubeEmbed source={annotation.youtube_source || ""} />;

    default:
      return null;
  }
}

// ─── Main block ───────────────────────────────────────────────────────────────

export default function InteractiveTextBlock({
  data,
}: {
  data: Record<string, unknown>;
}) {
  const text = (data.text as string) || "";
  const annotations = (data.annotations as InteractiveAnnotation[]) || [];
  const [activeAnnotation, setActiveAnnotation] =
    useState<InteractiveAnnotation | null>(null);

  const annotationMap = useMemo(
    () => new Map(annotations.map((a) => [a.id, a])),
    [annotations]
  );

  const segments = useMemo(() => parseAnnotatedHTML(text), [text]);

  // Fallback: no annotations → plain HTML paragraph
  if (annotations.length === 0) {
    return (
      <p
        className="text-slate-700 dark:text-slate-300 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: text }}
      />
    );
  }

  return (
    <>
      <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
        {segments.map((seg, i) => {
          if (seg.kind === "text") {
            return (
              <span
                key={i}
                dangerouslySetInnerHTML={{ __html: seg.html }}
              />
            );
          }

          const ann = annotationMap.get(seg.id);
          if (!ann) {
            // Orphaned span — render plain text
            return <span key={i}>{seg.innerText}</span>;
          }

          return (
            <span key={i} className="inline">
              {/* Highlighted clickable word(s) */}
              <button
                onClick={() => setActiveAnnotation(ann)}
                className="relative inline text-primary-700 dark:text-primary-400 bg-primary-50 dark:bg-primary-900/25 border-b-2 border-primary-400 dark:border-primary-500 rounded-sm px-0.5 cursor-pointer transition-colors hover:bg-primary-100 dark:hover:bg-primary-900/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
                title={ann.modal_title}
              >
                {seg.innerText}
              </button>
              {/* Magnifying glass icon */}
              <button
                onClick={() => setActiveAnnotation(ann)}
                aria-label={`Open annotation: ${ann.modal_title}`}
                className="inline-flex items-center justify-center w-4 h-4 ml-0.5 rounded-full bg-primary-100 dark:bg-primary-900/40 text-primary-600 dark:text-primary-400 hover:bg-primary-200 dark:hover:bg-primary-800/60 transition-colors cursor-pointer align-super"
                style={{ fontSize: "0.6rem" }}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="w-2.5 h-2.5"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            </span>
          );
        })}
      </p>

      <Modal
        isOpen={!!activeAnnotation}
        onClose={() => setActiveAnnotation(null)}
        title={activeAnnotation?.modal_title || "Annotation"}
        size="lg"
      >
        {activeAnnotation && (
          <AnnotationModalContent annotation={activeAnnotation} />
        )}
      </Modal>
    </>
  );
}
