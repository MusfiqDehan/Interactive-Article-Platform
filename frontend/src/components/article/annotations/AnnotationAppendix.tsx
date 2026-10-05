import { annotationDomId } from "@/lib/annotations";
import { normalizeMediaUrl } from "@/lib/media";
import type { AnnotationEntry } from "@/lib/public-types";

/**
 * Server-rendered "Notes & annotations" section.
 *
 * A native `<details>` per annotation. Chosen over the alternatives on purpose:
 *
 *   <template>      inert content, explicitly not indexed -- non-starter
 *   <noscript>      largely ignored; duplicating content there reads as cloaking
 *   display:none    indexed, but Google has said it may be discounted
 *   .sr-only        abuses a screen-reader pattern and strands no-JS readers
 *   <details>       fully indexed under mobile-first indexing, native, keyboard
 *                   accessible, works with zero JS -- and is semantically exactly
 *                   what an annotation is: a disclosure
 *
 * The client `AnnotationProvider` hides this on hydration and takes over with
 * modals, so JS users get the richer experience while the HTML stays complete.
 * Stable `#annotation-<id>` anchors also make notes deep-linkable, which is a
 * genuine reader feature rather than an SEO trick.
 */
export function AnnotationAppendix({
  annotations,
}: {
  annotations: AnnotationEntry[];
}) {
  const usable = annotations.filter((a) => a.id && (a.html || a.plain || a.media));
  if (usable.length === 0) return null;

  return (
    <section
      data-annotation-appendix
      aria-label="Notes and annotations"
      className="mt-16 border-t border-slate-200 pt-8 dark:border-slate-700"
    >
      <h2 className="mb-6 font-display text-2xl font-bold text-slate-900 dark:text-slate-100">
        Notes &amp; annotations
      </h2>
      <div className="space-y-3">
        {usable.map((annotation) => (
          <AnnotationDisclosure key={annotation.id} annotation={annotation} />
        ))}
      </div>
    </section>
  );
}

export function AnnotationDisclosure({
  annotation,
}: {
  annotation: AnnotationEntry;
}) {
  const summary =
    annotation.title || annotation.label || `Note ${annotation.id}`;

  return (
    <details
      id={annotationDomId(annotation.id)}
      data-annotation-id={annotation.id}
      className="group rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/40"
    >
      <summary className="cursor-pointer list-none font-medium text-slate-900 marker:content-none dark:text-slate-100">
        <span className="mr-2 inline-block text-primary-600 transition-transform group-open:rotate-90 dark:text-primary-400">
          ▸
        </span>
        {summary}
        {annotation.label && annotation.label !== summary && (
          <span className="ml-2 text-sm font-normal text-slate-500 dark:text-slate-400">
            — “{annotation.label}”
          </span>
        )}
      </summary>

      <div className="mt-3 space-y-3 pl-6">
        {annotation.media?.type === "image" && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={normalizeMediaUrl(annotation.media.url)}
            alt={annotation.media.alt || summary}
            className="w-full max-w-xl rounded-lg"
            loading="lazy"
          />
        )}
        {annotation.media && annotation.media.type !== "image" && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            <a
              href={normalizeMediaUrl(annotation.media.url)}
              className="underline"
              rel="noopener"
            >
              {annotation.media.type === "youtube" ? "Watch the video" : `Open ${annotation.media.type}`}
            </a>
          </p>
        )}
        {annotation.html ? (
          <div
            className="prose prose-slate max-w-none dark:prose-invert"
            dangerouslySetInnerHTML={{ __html: annotation.html }}
          />
        ) : annotation.plain ? (
          <p className="text-slate-700 dark:text-slate-300">{annotation.plain}</p>
        ) : null}
      </div>
    </details>
  );
}
