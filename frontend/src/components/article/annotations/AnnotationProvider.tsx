"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import Modal from "@/components/ui/Modal";
import { annotationDomId } from "@/lib/annotations";
import { normalizeMediaUrl } from "@/lib/media";
import type { AnnotationEntry } from "@/lib/public-types";

/**
 * One modal for the whole article, driven by context.
 *
 * Previously every annotated block rendered its own `<Modal>`, so a typical
 * article carried a dozen-plus modal instances. More importantly, `Modal`
 * returns null while closed, so annotation bodies were absent from the DOM
 * entirely until a click -- invisible to crawlers and to no-JS readers.
 *
 * Now the server renders every annotation into a `<details>` appendix, and this
 * provider hides those disclosures **on hydration** (never on the server) and
 * takes over with the richer modal experience. Identical HTML is served to
 * Googlebot and to browsers; JS clients get a progressive enhancement, which is
 * exactly what progressive enhancement is for. It is not cloaking.
 */

interface AnnotationContextValue {
  open: (id: string) => void;
  has: (id: string) => boolean;
}

const AnnotationContext = createContext<AnnotationContextValue>({
  open: () => {},
  has: () => false,
});

export function useAnnotations() {
  return useContext(AnnotationContext);
}

export function AnnotationProvider({
  annotations,
  children,
}: {
  annotations: AnnotationEntry[];
  children: React.ReactNode;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const byId = useMemo(
    () => new Map(annotations.filter((a) => a.id).map((a) => [a.id, a])),
    [annotations],
  );

  const open = useCallback((id: string) => setActiveId(id), []);
  const has = useCallback((id: string) => byId.has(id), [byId]);

  // Hide the server-rendered disclosures once JS is running. Doing this in an
  // effect (rather than server-side) is what keeps the SSR HTML complete.
  useEffect(() => {
    const hidden: HTMLElement[] = [];
    for (const annotation of annotations) {
      if (!annotation.id) continue;
      const el = document.getElementById(annotationDomId(annotation.id));
      if (el) {
        el.setAttribute("hidden", "");
        hidden.push(el);
      }
    }
    const appendix = document.querySelector<HTMLElement>("[data-annotation-appendix]");
    appendix?.setAttribute("hidden", "");

    return () => {
      hidden.forEach((el) => el.removeAttribute("hidden"));
      appendix?.removeAttribute("hidden");
    };
  }, [annotations]);

  // Deep links: /articles/x#annotation-a1 opens that note.
  //
  // The location hash is an external system, so an effect is the right tool --
  // but it must also track `hashchange`, or a link to another annotation from
  // within the same page silently does nothing (the appendix anchors are exactly
  // such links). The initial read stays synchronous so an arriving deep link
  // opens on first paint rather than flashing closed.
  useEffect(() => {
    const syncFromHash = () => {
      const hash = window.location.hash.replace("#", "");
      if (!hash.startsWith("annotation-")) return;
      const id = hash.slice("annotation-".length);
      if (byId.has(id)) setActiveId(id);
    };

    syncFromHash();
    window.addEventListener("hashchange", syncFromHash);
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, [byId]);

  const active = activeId ? byId.get(activeId) : null;

  return (
    <AnnotationContext.Provider value={{ open, has }}>
      {children}
      <Modal
        isOpen={Boolean(active)}
        onClose={() => setActiveId(null)}
        title={active?.title || "Note"}
        size="lg"
      >
        {active ? <AnnotationBody annotation={active} /> : null}
      </Modal>
    </AnnotationContext.Provider>
  );
}

function AnnotationBody({ annotation }: { annotation: AnnotationEntry }) {
  const media = annotation.media;

  return (
    <div className="space-y-4">
      {media?.type === "image" && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={normalizeMediaUrl(media.url)}
          alt={media.alt || annotation.title}
          className="w-full rounded-xl"
          loading="lazy"
        />
      )}
      {media?.type === "audio" && (
        <audio controls preload="metadata" className="w-full">
          <source src={normalizeMediaUrl(media.url)} />
        </audio>
      )}
      {media?.type === "video" && (
        <video controls preload="metadata" className="w-full rounded-xl">
          <source src={normalizeMediaUrl(media.url)} />
        </video>
      )}
      {media?.type === "youtube" && (
        <div className="relative w-full aspect-video">
          <iframe
            src={toEmbedUrl(media.url)}
            title={annotation.title}
            className="absolute inset-0 h-full w-full rounded-xl"
            allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"
            allowFullScreen
            loading="lazy"
          />
        </div>
      )}
      {annotation.html && (
        <div
          className="prose prose-slate dark:prose-invert max-w-none"
          dangerouslySetInnerHTML={{ __html: annotation.html }}
        />
      )}
    </div>
  );
}

function toEmbedUrl(source: string): string {
  const watch = source.match(/[?&]v=([^&]+)/);
  const short = source.match(/youtu\.be\/([^?&/]+)/);
  const embed = source.match(/\/embed\/([^?&/]+)/);
  const id = watch?.[1] || short?.[1] || embed?.[1] || "";
  return `https://www.youtube-nocookie.com/embed/${id}`;
}
