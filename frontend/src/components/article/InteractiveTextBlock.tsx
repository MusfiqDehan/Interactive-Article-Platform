"use client";

import { useState } from "react";
import Modal from "@/components/ui/Modal";
import { InteractiveAnnotation } from "@/lib/types";

export default function InteractiveTextBlock({ data }: { data: Record<string, unknown> }) {
  const text = (data.text as string) || "";
  const annotations = (data.annotations as InteractiveAnnotation[]) || [];
  const [activeAnnotation, setActiveAnnotation] = useState<InteractiveAnnotation | null>(null);

  if (annotations.length === 0) {
    return (
      <p
        className="text-slate-700 dark:text-slate-300 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: text }}
      />
    );
  }

  // Build the text with clickable spans for annotations
  // Strip HTML tags for annotation processing, then re-apply
  const plainText = text.replace(/<[^>]*>/g, "");
  const sortedAnnotations = [...annotations].sort((a, b) => a.start - b.start);

  const segments: React.ReactNode[] = [];
  let lastIndex = 0;

  sortedAnnotations.forEach((annotation, i) => {
    // Add text before this annotation
    if (annotation.start > lastIndex) {
      segments.push(
        <span key={`text-${i}`}>{plainText.slice(lastIndex, annotation.start)}</span>
      );
    }

    // Add the clickable annotation
    segments.push(
      <button
        key={`annotation-${i}`}
        onClick={() => setActiveAnnotation(annotation)}
        className="relative inline-block text-primary-600 dark:text-primary-400 font-medium underline decoration-primary-300 dark:decoration-primary-700 decoration-2 underline-offset-2 hover:decoration-primary-500 cursor-pointer transition-all hover:bg-primary-50 dark:hover:bg-primary-900/30 rounded px-0.5 -mx-0.5"
        title="Click for more details"
      >
        {plainText.slice(annotation.start, annotation.end)}
        <span className="absolute -top-1 -right-1 w-2 h-2 bg-primary-500 rounded-full animate-pulse" />
      </button>
    );

    lastIndex = annotation.end;
  });

  // Add remaining text
  if (lastIndex < plainText.length) {
    segments.push(<span key="text-end">{plainText.slice(lastIndex)}</span>);
  }

  return (
    <>
      <p className="text-slate-700 dark:text-slate-300 leading-relaxed">{segments}</p>

      <Modal
        isOpen={!!activeAnnotation}
        onClose={() => setActiveAnnotation(null)}
        title={activeAnnotation?.modal_title || "More Information"}
        size="lg"
      >
        <div
          className="prose prose-slate dark:prose-invert max-w-none"
          dangerouslySetInnerHTML={{ __html: activeAnnotation?.modal_content || "" }}
        />
      </Modal>
    </>
  );
}
