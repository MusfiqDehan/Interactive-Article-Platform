import { getSiteSafe } from "@/lib/api.server";
import { publicEnv } from "@/lib/env.server";

export const dynamic = "force-dynamic";

/**
 * robots.txt owned as a route handler so we can:
 * - point AI crawlers at /llms.txt
 * - honour SiteSettings.allow_ai_crawlers
 * - append SiteSettings.robots_extra without fighting MetadataRoute.Robots
 */
export async function GET() {
  let baseUrl = publicEnv.siteUrl;
  let allowAi = true;
  let extra = "";

  try {
    const site = await getSiteSafe();
    baseUrl = site.base_url || baseUrl;
    allowAi = site.allow_ai_crawlers;
    extra = (site.robots_extra || "").trim();
  } catch {
    /* fall back to the configured origin */
  }

  const origin = baseUrl.replace(/\/$/, "");

  const aiBots = ["GPTBot", "ChatGPT-User", "CCBot", "ClaudeBot", "Google-Extended", "Applebot-Extended", "PerplexityBot"];

  const aiBlock = allowAi
    ? aiBots
        .map(
          (bot) =>
            `User-agent: ${bot}\nAllow: /\nAllow: /llms.txt\nDisallow: /studio/\nDisallow: /dashboard/\nDisallow: /login\nDisallow: /register`,
        )
        .join("\n\n")
    : aiBots.map((bot) => `User-agent: ${bot}\nDisallow: /`).join("\n\n");

  const body = `# Storyloom / Meridian
# LLMs-Txt: ${origin}/llms.txt

User-agent: *
Allow: /
Allow: /llms.txt
Allow: /og/
Disallow: /studio/
Disallow: /dashboard/
Disallow: /api/
Disallow: /login
Disallow: /register
Disallow: /*?page=
Disallow: /*?cursor=
Disallow: /search?

${aiBlock}

Sitemap: ${origin}/sitemap.xml
Host: ${origin}
${extra ? `\n${extra}\n` : ""}`;

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
