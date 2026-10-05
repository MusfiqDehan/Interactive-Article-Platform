import { annotationMap, splitAnnotatedHtml } from "@/lib/annotations";
import { normalizeMediaUrl } from "@/lib/media";
import type { AnnotationEntry, EditorBlock } from "@/lib/public-types";

import { AnnotationTrigger } from "./annotations/AnnotationTrigger";
import { HotspotOverlay } from "./islands/HotspotOverlay";
import { MediaChapters } from "./islands/MediaChapters";
import { YouTubeEmbed } from "./islands/YouTubeEmbed";

/**
 * Server-rendered article body.
 *
 * The old renderer was `"use client"` all the way down, so the entire article
 * -- text, headings, images, everything -- only existed after hydration. Here
 * every block is server HTML, and only the genuinely interactive pieces
 * (annotation triggers, hotspots, chapter seeking, the YouTube facade) are
 * client islands.
 */

const PROSE =
  "prose prose-slate dark:prose-invert max-w-none prose-lg prose-headings:font-display prose-a:text-primary-600 dark:prose-a:text-primary-400 prose-img:rounded-xl";

export function ServerBlockRenderer({
  blocks,
  annotations,
}: {
  blocks: EditorBlock[];
  annotations: AnnotationEntry[];
}) {
  if (!blocks || blocks.length === 0) {
    return (
      <div className="py-12 text-center text-slate-400 dark:text-slate-500">
        No content available.
      </div>
    );
  }

  const byId = annotationMap(annotations);
  const known = new Set(byId.keys());

  return (
    <div className={PROSE}>
      {blocks.map((block, index) => (
        <div key={block.id || index} className="mb-6">
          <Block block={block} known={known} />
        </div>
      ))}
    </div>
  );
}

function Block({
  block,
  known,
}: {
  block: EditorBlock;
  // Only the id set is needed here: the annotation bodies are rendered by the
  // appendix, and each inline trigger looks its own entry up from context.
  known: ReadonlySet<string>;
}) {
  const data = (block.data || {}) as Record<string, any>;

  switch (block.type) {
    case "paragraph":
    case "interactive_text":
      return <AnnotatedText html={String(data.text ?? "")} known={known} />;

    case "header":
      return <Header text={String(data.text ?? "")} level={Number(data.level) || 2} />;

    case "list":
      return <List items={data.items ?? []} style={data.style} />;

    case "quote":
      return (
        <blockquote className="border-l-4 border-primary-500 pl-4 italic">
          <div dangerouslySetInnerHTML={{ __html: String(data.text ?? "") }} />
          {data.caption ? (
            <cite className="mt-2 block text-sm not-italic text-slate-500">
              <span dangerouslySetInnerHTML={{ __html: String(data.caption) }} />
            </cite>
          ) : null}
        </blockquote>
      );

    case "code":
      return (
        <pre className="overflow-x-auto rounded-xl bg-slate-900 p-4 text-slate-100">
          <code>{String(data.code ?? "")}</code>
        </pre>
      );

    case "delimiter":
      return (
        <div className="py-6 text-center text-2xl tracking-[0.5em] text-slate-400">
          ***
        </div>
      );

    case "image":
    case "interactive_image": {
      const url = data.file?.url || data.url || "";
      if (!url) return null;
      const hotspots = Array.isArray(data.hotspots) ? data.hotspots : [];
      return (
        <figure className="not-prose">
          <div className="relative">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={normalizeMediaUrl(String(url))}
              alt={String(data.caption || "")}
              className="w-full rounded-xl"
              loading="lazy"
            />
            {hotspots.length > 0 ? <HotspotOverlay hotspots={hotspots} /> : null}
          </div>
          {data.caption ? (
            <figcaption
              className="mt-2 text-center text-sm text-slate-500"
              dangerouslySetInnerHTML={{ __html: String(data.caption) }}
            />
          ) : null}
        </figure>
      );
    }

    case "audio":
    case "interactive_audio":
      return (
        <MediaShell
          kind="audio"
          url={String(data.file?.url || data.url || "")}
          caption={data.caption}
          chapters={data.chapters}
        />
      );

    case "video":
    case "interactive_video":
      return (
        <MediaShell
          kind="video"
          url={String(data.file?.url || data.url || "")}
          caption={data.caption}
          chapters={data.chapters}
        />
      );

    case "youtube":
    case "embed":
    case "interactive_youtube":
      return (
        <YouTubeEmbed
          source={String(data.source || data.embed || data.url || "")}
          caption={data.caption ? String(data.caption) : ""}
          chapters={Array.isArray(data.chapters) ? data.chapters : []}
        />
      );

    default:
      // Unknown block types render nothing rather than breaking the page.
      return null;
  }
}

/** Paragraph text with annotation spans replaced by client triggers. */
function AnnotatedText({
  html,
  known,
}: {
  html: string;
  known: ReadonlySet<string>;
}) {
  const { segments, hasAnnotations } = splitAnnotatedHtml(html, known);

  // Fast path: no annotations means no islands, so this stays pure server HTML.
  if (!hasAnnotations) {
    return <p dangerouslySetInnerHTML={{ __html: html }} />;
  }

  return (
    <p>
      {segments.map((segment, index) =>
        segment.kind === "html" ? (
          <span key={index} dangerouslySetInnerHTML={{ __html: segment.html }} />
        ) : (
          <AnnotationTrigger key={index} id={segment.id} label={segment.label} />
        ),
      )}
    </p>
  );
}

function Header({ text, level }: { text: string; level: number }) {
  // Clamp to h2-h4: the page title is already the h1, and a second one in the
  // body competes with it.
  const safeLevel = Math.min(Math.max(level, 2), 4);
  const Tag = `h${safeLevel}` as "h2" | "h3" | "h4";
  return <Tag dangerouslySetInnerHTML={{ __html: text }} />;
}

function List({ items, style }: { items: unknown[]; style?: string }) {
  const Tag = style === "ordered" ? "ol" : "ul";
  return (
    <Tag>
      {(items || []).map((item, index) => {
        const content =
          typeof item === "string"
            ? item
            : String((item as Record<string, unknown>)?.content ?? "");
        return <li key={index} dangerouslySetInnerHTML={{ __html: content }} />;
      })}
    </Tag>
  );
}

function MediaShell({
  kind,
  url,
  caption,
  chapters,
}: {
  kind: "audio" | "video";
  url: string;
  caption?: unknown;
  chapters?: unknown;
}) {
  if (!url) return null;
  const list = Array.isArray(chapters) ? chapters : [];
  const src = normalizeMediaUrl(url);

  return (
    <figure className="not-prose space-y-3">
      {list.length > 0 ? (
        // Chapters need to seek the element, so that variant is an island.
        <MediaChapters kind={kind} src={src} chapters={list} />
      ) : kind === "audio" ? (
        <audio controls preload="metadata" className="w-full">
          <source src={src} />
        </audio>
      ) : (
        <video controls preload="metadata" className="w-full rounded-xl">
          <source src={src} />
        </video>
      )}
      {caption ? (
        <figcaption
          className="text-center text-sm text-slate-500"
          dangerouslySetInnerHTML={{ __html: String(caption) }}
        />
      ) : null}
    </figure>
  );
}
