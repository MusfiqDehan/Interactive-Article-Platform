"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { PublicEnv } from "./env.server";

/**
 * Carries runtime configuration from the server to client components.
 *
 * A server component reads the environment at *request* time and passes this
 * object down as a plain prop; Next serializes it into the RSC payload. That
 * is what lets one built image serve any domain -- unlike `NEXT_PUBLIC_*`,
 * which is frozen into the bundle at build time.
 */

const fallback: PublicEnv = {
  siteUrl: "",
  apiBase: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8003/api",
  siteSlug: "default",
  eventsApiKey: "",
};

const RuntimeConfigContext = createContext<PublicEnv>(fallback);

/**
 * Runtime config for code that cannot use a hook.
 *
 * The Axios client in `studio-api.ts` is a module singleton, not a component,
 * so it cannot read context -- but it still needs the runtime-resolved API
 * base, since the whole point of this provider is that the base URL is *not*
 * baked into the bundle.
 *
 * The values are read back off `<html data-api-base=...>`, which the root
 * layout stamps on the server. A module-level variable assigned during render
 * would be simpler to write and wrong twice over: mutating module state during
 * render is exactly what React's compiler rules forbid, and moving the
 * assignment into an effect would not help, because child effects run *before*
 * parent effects -- so a child calling `studioApi()` would still read `null`.
 * The DOM attribute is present before any JavaScript runs, so there is no
 * ordering question at all.
 */
export function publicEnvFromWindow(): PublicEnv | null {
  if (typeof document === "undefined") return null;
  const { apiBase, siteUrl, siteSlug, eventsKey } = document.documentElement.dataset;
  if (!apiBase) return null;
  return {
    apiBase,
    siteUrl: siteUrl ?? "",
    siteSlug: siteSlug ?? "default",
    eventsApiKey: eventsKey ?? "",
  };
}

export function RuntimeConfigProvider({
  value,
  children,
}: {
  value: PublicEnv;
  children: ReactNode;
}) {
  return (
    <RuntimeConfigContext.Provider value={value}>
      {children}
    </RuntimeConfigContext.Provider>
  );
}

export function useRuntimeConfig(): PublicEnv {
  return useContext(RuntimeConfigContext);
}
