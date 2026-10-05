import "server-only";

/**
 * Environment, split into three tiers.
 *
 * The problem this solves: `NEXT_PUBLIC_*` variables are inlined into the
 * client bundle at build time, so one Docker image only ever works for one
 * domain. That blocks multi-site deployment outright, and it silently ignores
 * the runtime `environment:` block in compose -- a trap for whoever changes it
 * next and cannot work out why nothing happened.
 *
 *   1. Server-only, read at runtime   -- API base, keys, secrets. Never inlined.
 *   2. Server-read, client-surfaced   -- handed to the browser through
 *                                        RuntimeConfigProvider at request time.
 *   3. Legacy NEXT_PUBLIC_*           -- kept until the Axios layer migrates.
 *
 * Server fetches go over the container network (`http://backend:8003`) rather
 * than back out through the public domain, avoiding a pointless TLS handshake
 * and a hard dependency on external DNS from inside the container.
 */

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. ` +
        `Set it in the container environment (not as a build arg).`,
    );
  }
  return value;
}

function optional(name: string, fallback = ""): string {
  return process.env[name] || fallback;
}

/** Tier 1: never leaves the server. */
export const serverEnv = {
  /** Container-network origin, e.g. http://backend:8003/api/v1 */
  apiUrl: optional(
    "CMS_INTERNAL_API_URL",
    optional("NEXT_PUBLIC_API_BASE_URL", "http://backend:8003/api").replace(
      /\/api\/?$/,
      "/api/v1",
    ),
  ).replace(/\/$/, ""),
  /** This site's own public delivery key. */
  apiKey: optional("CMS_SITE_API_KEY"),
  /** Shared with the backend's SiteSettings.revalidate_secret. */
  revalidateSecret: optional("CMS_REVALIDATE_SECRET"),
};

/** Tier 2: safe to serialize into the RSC payload. */
export const publicEnv = {
  siteUrl: optional("PUBLIC_SITE_URL", "http://localhost:3003").replace(/\/$/, ""),
  apiBase: optional(
    "PUBLIC_API_BASE_URL",
    optional("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8003/api"),
  ).replace(/\/$/, ""),
  siteSlug: optional("PUBLIC_SITE_SLUG", "default"),
  /**
   * A *separate*, write-events-only key for the analytics beacon.
   *
   * Deliberately not `serverEnv.apiKey`: that one can read every article
   * including unpublished ones, and the beacon runs in the browser where any
   * reader can see it. Empty disables analytics rather than falling back to
   * the read key.
   */
  eventsApiKey: optional("PUBLIC_EVENTS_API_KEY"),
};

export type PublicEnv = typeof publicEnv;

export { required };
