import { getSitemapShard } from "@/lib/api.server";

/**
 * One sitemap shard, at `/sitemap/<n>.xml`.
 *
 * Written as an explicit route handler rather than via `app/sitemap.ts` +
 * `generateSitemaps`: that metadata file also claims `/sitemap.xml`, which
 * collides with the index route and leaves the index itself unrouted (404).
 * Owning both paths here keeps the pair coherent.
 */

/**
 * Rendered per request. Next 15 stopped caching GET route handlers by default,
 * and that default is the right one here: one built image serves every tenant,
 * so a shard cached at the framework layer would hand site B the sitemap of
 * whichever site warmed the cache first. The `Cache-Control` header below still
 * gets the CDN caching -- keyed on host, which is the correct granularity.
 */
export const dynamic = "force-dynamic";

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ shard: string }> },
) {
  // Accept both "0" and "0.xml".
  const { shard } = await params;
  const index = Number.parseInt(shard.replace(/\.xml$/, ""), 10);
  if (Number.isNaN(index) || index < 0) {
    return new Response("Not found", { status: 404 });
  }

  let entries: Awaited<ReturnType<typeof getSitemapShard>> = [];
  try {
    entries = await getSitemapShard(index);
  } catch {
    entries = [];
  }

  const urls = entries
    .map((entry) => {
      const parts = [`    <loc>${escapeXml(entry.url)}</loc>`];
      if (entry.lastmod) parts.push(`    <lastmod>${entry.lastmod}</lastmod>`);
      if (entry.changefreq)
        parts.push(`    <changefreq>${entry.changefreq}</changefreq>`);
      if (entry.priority != null)
        parts.push(`    <priority>${entry.priority}</priority>`);
      if (entry.image) {
        parts.push(
          `    <image:image><image:loc>${escapeXml(entry.image)}</image:loc></image:image>`,
        );
      }
      return `  <url>\n${parts.join("\n")}\n  </url>`;
    })
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
${urls}
</urlset>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, s-maxage=900, stale-while-revalidate=3600",
    },
  });
}
