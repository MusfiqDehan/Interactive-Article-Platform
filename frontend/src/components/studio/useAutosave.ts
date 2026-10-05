"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { StaleContentError, saveArticle, type StudioArticle } from "@/lib/studio-api";

export type SaveState =
  | { kind: "idle" }
  | { kind: "dirty" }
  | { kind: "saving" }
  | { kind: "saved"; at: number }
  | { kind: "conflict"; currentVersion: string }
  | { kind: "error"; message: string };

const DEBOUNCE_MS = 2000;

/**
 * Debounced autosave with optimistic-concurrency handling.
 *
 * Sends the `content_hash` the article was loaded at as `If-Match`, and stops
 * dead on a 409 instead of retrying. Retrying a conflict is the one thing that
 * must not happen: the second attempt would carry the server's new version and
 * succeed, silently destroying the other tab's work -- exactly the failure the
 * header exists to prevent.
 */
export function useAutosave(slug: string | null, baseVersion: string | null) {
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const versionRef = useRef<string | null>(baseVersion);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef<Partial<StudioArticle> | null>(null);
  const inFlightRef = useRef(false);
  const stateRef = useRef<SaveState>(state);
  stateRef.current = state;

  useEffect(() => {
    versionRef.current = baseVersion;
  }, [baseVersion]);

  const flush = useCallback(async () => {
    if (!slug || !pendingRef.current || inFlightRef.current) return;
    // A conflict is terminal until the user resolves it; queuing more saves
    // behind it would pile up writes against a version we know is stale.
    if (stateRef.current.kind === "conflict") return;

    const patch = pendingRef.current;
    pendingRef.current = null;
    inFlightRef.current = true;
    setState({ kind: "saving" });

    try {
      const saved = await saveArticle(slug, patch, versionRef.current ?? undefined);
      versionRef.current = saved.content_hash;
      setState({ kind: "saved", at: Date.now() });
      return saved;
    } catch (error) {
      // Put the edit back either way, so nothing typed is ever dropped on the
      // floor and "keep mine" / retry has something to resend.
      pendingRef.current = { ...patch, ...(pendingRef.current ?? {}) };
      if (error instanceof StaleContentError) {
        setState({ kind: "conflict", currentVersion: error.currentVersion });
      } else {
        setState({
          kind: "error",
          message: "Could not save. Your changes are still here — retrying will resend them.",
        });
      }
    } finally {
      inFlightRef.current = false;
    }
  }, [slug]);

  const queue = useCallback(
    (patch: Partial<StudioArticle>) => {
      pendingRef.current = { ...(pendingRef.current ?? {}), ...patch };
      setState((prev) => (prev.kind === "conflict" ? prev : { kind: "dirty" }));
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(flush, DEBOUNCE_MS);
    },
    [flush],
  );

  /** Resolve a conflict by overwriting the server's version with ours. */
  const keepMine = useCallback(async () => {
    const current = stateRef.current;
    if (current.kind !== "conflict") return;
    versionRef.current = current.currentVersion;
    setState({ kind: "dirty" });
    stateRef.current = { kind: "dirty" };
    await flush();
  }, [flush]);

  const saveNow = useCallback(async () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    return flush();
  }, [flush]);

  // Warn before leaving with unsaved work. The debounce window is only two
  // seconds, but a failed or conflicted save can leave changes pending
  // indefinitely.
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      const kind = stateRef.current.kind;
      const unsaved =
        pendingRef.current !== null &&
        (kind === "dirty" || kind === "conflict" || kind === "error");
      if (unsaved) event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return { state, queue, saveNow, keepMine, markVersion: (v: string) => {
    versionRef.current = v;
  } };
}
