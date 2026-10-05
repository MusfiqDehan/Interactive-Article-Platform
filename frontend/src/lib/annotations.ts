/**
 * Splitting paragraph HTML around inline annotation spans.
 *
 * Runs on the **server**, which is the whole point: the previous version of
 * this logic lived inside a `"use client"` component, so annotation markers
 * only appeared after hydration, and their bodies only entered the DOM when a
 * reader clicked. A crawler saw neither.
 *
 * Annotation *bodies* now come from the server-computed `annotations_index`
 * rather than being parsed out of a `data-annotation` attribute. That attribute
 * survives a sanitizer round trip only by luck (nh3 decodes `&lt;` inside it),
 * so it is a fallback here, not the source of truth.
 */

import type { AnnotationEntry } from "./public-types";

export type Segment =
  | { kind: "html"; html: string }
  | { kind: "annotation"; id: string; label: string };

/** Editor-only magnifier spans; removed before matching so annotation spans contain no nested `</span>`. */
const ICON_SPAN = /<span[^>]*?\bdata-annotation-icon\b[^>]*?>[\s\S]*?<\/span>/g;

const ANNOTATION_SPAN =
  /<span\s([^>]*?\bdata-annotation-id="([^"]+)"[^>]*?)>([\s\S]*?)<\/span>/g;

export function stripIconSpans(html: string): string {
  return (html || "").replace(ICON_SPAN, "");
}

export function stripTags(html: string): string {
  return (html || "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&#x27;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Split paragraph HTML into renderable segments.
 *
 * `known` is the set of annotation ids present in `annotations_index`; a span
 * referencing an unknown id degrades to plain text rather than rendering a
 * trigger that would open an empty modal.
 */
export function splitAnnotatedHtml(
  html: string,
  known: ReadonlySet<string>,
): { segments: Segment[]; hasAnnotations: boolean } {
  const cleaned = stripIconSpans(html || "");
  const segments: Segment[] = [];
  let lastIndex = 0;
  let found = false;
  let match: RegExpExecArray | null;

  // Fresh lastIndex per call: the regex is module-level and /g is stateful.
  ANNOTATION_SPAN.lastIndex = 0;

  while ((match = ANNOTATION_SPAN.exec(cleaned)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: "html", html: cleaned.slice(lastIndex, match.index) });
    }

    const id = match[2];
    const inner = match[3];

    if (known.has(id)) {
      segments.push({ kind: "annotation", id, label: stripTags(inner) });
      found = true;
    } else {
      segments.push({ kind: "html", html: inner });
    }
    lastIndex = ANNOTATION_SPAN.lastIndex;
  }

  if (lastIndex < cleaned.length) {
    segments.push({ kind: "html", html: cleaned.slice(lastIndex) });
  }

  return { segments, hasAnnotations: found };
}

export function annotationMap(
  entries: AnnotationEntry[],
): Map<string, AnnotationEntry> {
  return new Map(entries.filter((e) => e.id).map((e) => [e.id, e]));
}

/** DOM id for an annotation's server-rendered disclosure. */
export function annotationDomId(id: string): string {
  return `annotation-${id}`;
}
