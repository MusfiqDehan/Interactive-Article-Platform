"use client";

import { track } from "@/lib/analytics";
import { annotationDomId } from "@/lib/annotations";

import { useAnnotations } from "./AnnotationProvider";

/**
 * The in-text marker for an annotation.
 *
 * `aria-describedby` points at the server-rendered disclosure, so assistive
 * technology can reach the note's text even before the modal opens.
 */
export function AnnotationTrigger({
  id,
  label,
  articleId,
}: {
  id: string;
  label: string;
  articleId?: number;
}) {
  const { open } = useAnnotations();

  return (
    <button
      type="button"
      onClick={() => {
        open(id);
        // The event behind the interaction rate -- the one number that says
        // whether the interactive format is used rather than merely served.
        track("annotation_open", { article_id: articleId, target_id: id });
      }}
      aria-describedby={annotationDomId(id)}
      aria-haspopup="dialog"
      className="group mx-0.5 inline-flex items-baseline gap-1 rounded border-b-2 border-dotted border-primary-400 bg-primary-50/60 px-1 font-medium text-primary-800 transition-colors hover:bg-primary-100 dark:border-primary-500 dark:bg-primary-900/30 dark:text-primary-200 dark:hover:bg-primary-900/60"
    >
      <span>{label}</span>
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-3 w-3 shrink-0 self-center opacity-60 transition-opacity group-hover:opacity-100"
      >
        <path
          fillRule="evenodd"
          d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
          clipRule="evenodd"
        />
      </svg>
    </button>
  );
}
