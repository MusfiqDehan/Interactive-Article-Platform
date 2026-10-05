import "server-only";

import { notFound } from "next/navigation";

import { PLATFORM } from "./brand";
import { serverEnv } from "./env.server";
import { normalizeSlug } from "./slug";
import type {
  CursorPage,
  PublicArticle,
  PublicArticleListItem,
  PublicCategory,
  RedirectRule,
  SiteConfig,
  SitemapEntry,
  SitemapShard,
  SlugEntry,
} from "./public-types";

/**
 * Server-side data access for the public delivery API.
 *
 * Deliberately separate from `src/lib/api.ts` (Axios): that layer reads
 * `localStorage` and installs interceptors, neither of which exists on the
 * server. Two layers, one boundary, no shared mutable state.
 */

export class CmsError extends Error {
  constructor(
    readonly status: number,
    readonly body: string,
  ) {
    super(`CMS request failed with ${status}`);
  }
}

type FetchOptions = {
  /** Seconds; `false` opts out of the time-based cache (tags still apply). */
  revalidate?: number | false;
  tags?: string[];
  query?: Record<string, string | number | boolean | undefined | null>;
};

async function cmsFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const url = new URL(serverEnv.apiUrl + path);
  for (const [key, value] of Object.entries(opts.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const res = await fetch(url, {
    headers: {
      "X-API-Key": serverEnv.apiKey,
      Accept: "application/json",
    },
    next:
      opts.revalidate === false
        ? { tags: opts.tags }
        : { revalidate: opts.revalidate ?? 300, tags: opts.tags },
  });

  // A real 404 status, so Next renders not-found.tsx and crawlers see a 404 --
  // the current client-rendered "not found" div returns HTTP 200, and soft-404s
  // get indexed.
  if (res.status === 404) notFound();
  if (!res.ok) {
    throw new CmsError(res.status, await res.text().catch(() => ""));
  }
  return (await res.json()) as T;
}

/** Same as cmsFetch but returns null instead of throwing/404ing. */
async function cmsFetchOptional<T>(
  path: string,
  opts: FetchOptions = {},
): Promise<T | null> {
  try {
    return await cmsFetch<T>(path, opts);
  } catch {
    return null;
  }
}

// -- typed helpers: the only thing pages should import ---------------------

export function getArticle(slug: string) {
  // Encode once, here. Every caller passes a decoded slug; double-encoding
  // produces a 404 that only ever shows up for non-ASCII titles.
  const encoded = encodeURIComponent(normalizeSlug(slug));
  return cmsFetch<PublicArticle>(`/public/articles/${encoded}/`, {
    revalidate: 3600,
    tags: ["articles", `article:${normalizeSlug(slug)}`],
  });
}

export function getArticleOptional(slug: string) {
  const encoded = encodeURIComponent(normalizeSlug(slug));
  return cmsFetchOptional<PublicArticle>(`/public/articles/${encoded}/`, {
    revalidate: 3600,
    tags: ["articles", `article:${normalizeSlug(slug)}`],
  });
}

export function listArticles(query: FetchOptions["query"] = {}) {
  return cmsFetch<CursorPage<PublicArticleListItem>>("/public/articles/", {
    query,
    revalidate: 300,
    tags: ["articles"],
  });
}

export function getFeaturedArticles() {
  return cmsFetch<PublicArticleListItem[]>("/public/articles/featured/", {
    revalidate: 600,
    tags: ["articles"],
  });
}

export function getRelatedArticles(slug: string) {
  const encoded = encodeURIComponent(normalizeSlug(slug));
  return cmsFetchOptional<PublicArticleListItem[]>(
    `/public/articles/${encoded}/related/`,
    { revalidate: 3600, tags: ["articles"] },
  );
}

export function getAllSlugs() {
  return cmsFetch<SlugEntry[]>("/public/articles/slugs/", {
    revalidate: 3600,
    tags: ["articles", "sitemap"],
  });
}

export interface SearchHit {
  id: number;
  title: string;
  slug: string;
  path_slug: string;
  excerpt: string;
  category: string;
  tags: string[];
  reading_time: number;
  published_at: number;
}

export interface SearchResult {
  query: string;
  hits: SearchHit[];
  total: number;
  /** False when the engine is unreachable -- a different message to a reader
   *  than "nothing matched", and the page says so. */
  available: boolean;
}

/**
 * Server-side search.
 *
 * Deliberately uncached: a result set keyed on an arbitrary query string has
 * no reuse worth the storage, and a stale search result is worse than a slow
 * one. The browser's fast path queries Meilisearch directly with a tenant
 * token; this is the crawler, no-JS and fallback path.
 */
export function search(query: string, extra: Record<string, string> = {}) {
  return cmsFetch<SearchResult>("/public/search/", {
    query: { q: query, ...extra },
    revalidate: 0,
  });
}

export function getTags() {
  return cmsFetch<Array<{ id: number; name: string; slug: string; usage_count: number }>>(
    "/public/tags/",
    { revalidate: 3600, tags: ["tags"] },
  );
}

export function getCategories() {
  return cmsFetch<PublicCategory[]>("/public/categories/", {
    revalidate: 3600,
    tags: ["categories"],
  });
}

export function getCategory(slug: string) {
  const encoded = encodeURIComponent(normalizeSlug(slug));
  return cmsFetch<PublicCategory>(`/public/categories/${encoded}/`, {
    revalidate: 3600,
    tags: ["categories"],
  });
}

export function getSite() {
  return cmsFetch<SiteConfig>("/public/site/", {
    revalidate: 3600,
    tags: ["site"],
  });
}

/**
 * Site config that never throws.
 *
 * Static pages are prerendered inside the Docker image build, where the API is
 * not reachable. Hard-failing there would mean the image can only be built
 * while a backend happens to be running -- so these pages fall back and let ISR
 * fill in the real values on first revalidation.
 */
export async function getSiteSafe(): Promise<SiteConfig> {
  const site = await cmsFetchOptional<SiteConfig>("/public/site/", {
    revalidate: 3600,
    tags: ["site"],
  });
  if (site) return site;

  const { publicEnv } = await import("./env.server");
  return {
    name: PLATFORM.name,
    slug: publicEnv.siteSlug,
    base_url: publicEnv.siteUrl,
    locale: "en",
    site_title: PLATFORM.name,
    title_template: `%s | ${PLATFORM.name}`,
    default_meta_description: PLATFORM.description,
    default_og_image: `${publicEnv.siteUrl}${PLATFORM.ogImage}`,
    organization_jsonld: {},
    robots_extra: "",
    google_site_verification: "",
    allow_ai_crawlers: true,
  };
}

export function getCategoriesSafe() {
  return cmsFetchOptional<PublicCategory[]>("/public/categories/", {
    revalidate: 3600,
    tags: ["categories"],
  }).then((categories) => categories ?? []);
}

export function getRedirects() {
  return cmsFetch<RedirectRule[]>("/public/redirects/", {
    revalidate: 60,
    tags: ["redirects"],
  });
}

export function getSitemapShards() {
  return cmsFetch<{ shards: SitemapShard[] }>("/public/sitemap-index/", {
    revalidate: 900,
    tags: ["sitemap"],
  });
}

export function getSitemapShard(index: number) {
  return cmsFetch<SitemapEntry[]>(`/public/sitemap/${index}/`, {
    revalidate: 900,
    tags: ["sitemap"],
  });
}

export { cmsFetch, cmsFetchOptional };
