"use client";

import { useState, useMemo } from "react";
import Modal from "@/components/ui/Modal";
import { normalizeMediaUrl } from "@/lib/media";

interface InlineAnnotation {
  id: string;
  type: "text" | "image" | "audio" | "video" | "youtube";
  modal_title: string;
  modal_content?: string;
  image_url?: string;
  image_caption?: string;
  audio_url?: string;
  video_url?: string;
  youtube_source?: string;
}

type Segment =
  | { kind: "text"; html: string }
  | { kind: "annotation"; annotation: InlineAnnotation; innerText: string };

/** Strip editor-only icon spans (🔍) that the inline tool injects for UX. */
function stripIconSpans(html: string): string {
  return html.replace(
    /<span[^>]*?\bdata-annotation-icon\b[^>]*?>[\s\S]*?<\/span>/g,
    ""
  );
}

/**
 * Parse paragraph HTML and extract inline annotations whose metadata is stored
 * in a `data-annotation` attribute (JSON) on the wrapping `<span>`.
 *
 * Icon spans are stripped FIRST so that annotation `<span>`s have no nested
 * `</span>` tags — this lets the simple `([\s\S]*?)<\/span>` regex work
 * correctly.
 */
function parseInlineAnnotations(html: string): {
  segments: Segment[];
  hasAnnotations: boolean;
} {
  // Step 1 – remove icon spans so annotation spans have no nested </span>
  const cleaned = stripIconSpans(html);

  // Step 2 – find annotation spans (attribute order doesn't matter; we
  // capture the whole opening-tag attrs string and extract values from it)
  const regex =
    /<span\s([^>]*?\bdata-annotation-id="([^"]+)"[^>]*?)>([\s\S]*?)<\/span>/g;
  const segments: Segment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let found = false;

  while ((match = regex.exec(cleaned)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        kind: "text",
        html: cleaned.slice(lastIndex, match.index),
      });
    }

    const attrs = match[1];
    const innerText = match[3].trim();

    // Extract the data-annotation JSON from the attributes string
    const jsonMatch = attrs.match(/\bdata-annotation="([^"]*)"/);
    let annotation: InlineAnnotation | null = null;

    if (jsonMatch) {
      try {
        annotation = JSON.parse(
          jsonMatch[1]
            .replace(/&quot;/g, '"')
            .replace(/&amp;/g, "&")
            .replace(/&lt;/g, "<")
            .replace(/&gt;/g, ">")
        ) as InlineAnnotation;
      } catch {
        /* corrupted JSON – fall through */
      }
    }

    if (annotation) {
      segments.push({ kind: "annotation", annotation, innerText });
      found = true;
    } else {
      // No valid annotation data – render as plain text
      segments.push({ kind: "text", html: innerText });
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < cleaned.length) {
    segments.push({ kind: "text", html: cleaned.slice(lastIndex) });
  }

  return { segments, hasAnnotations: found };
}

/* ── Modal content by annotation type ──────────────────────────────────── */

function YouTubeEmbed({ source }: { source: string }) {
  let embedUrl = source;
  try {
    if (source.includes("youtube.com/watch")) {
      embedUrl = `https://www.youtube-nocookie.com/embed/${new URL(source).searchParams.get("v") || ""}`;
    } else if (source.includes("youtu.be/")) {
      embedUrl = `https://www.youtube-nocookie.com/embed/${source.split("youtu.be/")[1]?.split("?")[0] || ""}`;
    }
  } catch {
    /* ignore */
  }

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

function AnnotationModalContent({ annotation }: { annotation: InlineAnnotation }) {
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

/* ── Component ─────────────────────────────────────────────────────────── */

export default function ParagraphBlock({
  data,
}: {
  data: Record<string, unknown>;
}) {
  const text = (data.text as string) || "";
  const [activeAnnotation, setActiveAnnotation] =
    useState<InlineAnnotation | null>(null);

  const { segments, hasAnnotations } = useMemo(
    () => parseInlineAnnotations(text),
    [text]
  );

  // Fast path: plain paragraph with no inline annotations
  if (!hasAnnotations) {
    // Still strip any leftover icon spans before rendering
    const safeHtml = stripIconSpans(text);
    return (
      <p
        className="text-slate-700 dark:text-slate-300 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: safeHtml }}
      />
    );
  }

  return (
    <>
      <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
        {segments.map((seg, i) => {
          if (seg.kind === "text") {
            return (
              <span key={i} dangerouslySetInnerHTML={{ __html: seg.html }} />
            );
          }

          return (
            <span key={i} className="inline">
              <button
                onClick={() => setActiveAnnotation(seg.annotation)}
                className="relative inline text-primary-700 dark:text-primary-400 bg-primary-50 dark:bg-primary-900/25 border-b-2 border-primary-400 dark:border-primary-500 rounded-sm px-0.5 cursor-pointer transition-colors hover:bg-primary-100 dark:hover:bg-primary-900/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
                title={seg.annotation.modal_title}
              >
                {seg.innerText}
              </button>
              <button
                onClick={() => setActiveAnnotation(seg.annotation)}
                aria-label={`Open annotation: ${seg.annotation.modal_title}`}
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
