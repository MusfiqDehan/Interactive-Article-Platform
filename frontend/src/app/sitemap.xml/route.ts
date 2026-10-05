import { getSitemapShards } from "@/lib/api.server";
import { publicEnv } from "@/lib/env.server";

/**
 * Sitemap index.
 *
 * Owned explicitly rather than via `app/sitemap.ts` + `generateSitemaps`. That
 * metadata file claims `/sitemap.xml` for itself, so the two cannot coexist --
 * and under Next 14 it produced only the shards, leaving the index URL that
 * robots.txt advertises as a 404. Keeping both paths as route handlers means
 * the index and its shards stay in sync and are not at the mercy of that
 * convention changing again.
 *
 * Per request, for the same tenant-correctness reason as the shard route.
 */

export const dynamic = "force-dynamic";

export async function GET() {
  let baseUrl = publicEnv.siteUrl;
  let shards: { n: number; lastmod: string | null }[] = [];

  try {
    const [{ shards: fetched }, site] = await Promise.all([
      getSitemapShards(),
      import("@/lib/api.server").then((m) => m.getSiteSafe()),
    ]);
    shards = fetched;
    baseUrl = site.base_url || baseUrl;
  } catch {
    // Emit a valid, empty index rather than a 500: a broken sitemap is worse
    // than an empty one.
  }

  const entries = (shards.length > 0 ? shards : [{ n: 0, lastmod: null }])
    .map(
      (shard) =>
        `  <sitemap>\n    <loc>${baseUrl}/sitemap/${shard.n}.xml</loc>` +
        (shard.lastmod ? `\n    <lastmod>${shard.lastmod}</lastmod>` : "") +
        `\n  </sitemap>`,
    )
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${entries}
</sitemapindex>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, s-maxage=900, stale-while-revalidate=3600",
    },
  });
}
