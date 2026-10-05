"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * Fetch-on-key with **derived** loading state.
 *
 * The usual shape -- `useState` for data, another for `loading`, a `useEffect`
 * that flips both -- has a window after the key changes and before the effect
 * runs where `loading` is still false and `data` still holds the *previous*
 * key's result. The UI renders stale rows as though they were current, which is
 * exactly wrong on a screen whose filters are in the URL and change on every
 * keystroke.
 *
 * Storing the key alongside the result removes the window: `loading` is simply
 * "the result I hold is not for the key I want", which cannot disagree with
 * itself.
 *
 * A stale response is also discarded on arrival, so two in-flight requests
 * cannot resolve out of order and leave the slower one's data on screen.
 */
export function useStudioQuery<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
): {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  refresh: () => void;
} {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<{ key: string; data?: T; error?: string }>({
    key: "",
  });

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const key = useMemo(() => JSON.stringify([...deps, nonce]), [...deps, nonce]);

  useEffect(() => {
    let live = true;
    fetcher()
      .then((data) => live && setResult({ key, data }))
      .catch((err) =>
        live &&
        setResult({
          key,
          error:
            err?.response?.data?.detail ??
            err?.message ??
            "Something went wrong loading this.",
        }),
      );
    return () => {
      live = false;
    };
    // `fetcher` is intentionally not a dependency: it is re-created on every
    // render by every caller, and including it would refetch in a loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return {
    data: result.key === key ? result.data : undefined,
    error: result.key === key ? (result.error ?? null) : null,
    loading: result.key !== key,
    refresh,
  };
}
