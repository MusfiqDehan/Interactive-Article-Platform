import { getSiteSafe } from "@/lib/api.server";
import { PLATFORM, TENANT_PUBLICATION } from "@/lib/brand";
import { publicEnv } from "@/lib/env.server";
import { absoluteUrl } from "@/lib/seo";

export const dynamic = "force-dynamic";

/**
 * /llms.txt — a machine-readable map of this site for language models.
 *
 * Linked from robots.txt. Kept short on purpose: crawlers that honour this
 * file want orientation, not a dump of every article.
 */
export async function GET() {
  const site = await getSiteSafe();
  const base = site.base_url || publicEnv.siteUrl;
  const name = site.site_title || site.name || PLATFORM.name;
  const description =
    site.default_meta_description || PLATFORM.description;

  const body = `# ${name}

> ${description}

Storyloom is the bilingual CMS that powers this site. Meridian is the demo tenant publication — a journal of astronomy, technology, geopolitics, and system design.

## Primary pages

- [Platform](${absoluteUrl("/", base)}): ${PLATFORM.tagline}
- [Publication home](${absoluteUrl("/home", base)}): ${TENANT_PUBLICATION.tagline}
- [Articles](${absoluteUrl("/articles", base)}): published long-form
- [Categories](${absoluteUrl("/categories", base)}): topic index
- [Search](${absoluteUrl("/search", base)}): full-text search (do not index query URLs)

## Machine endpoints

- Sitemap: ${absoluteUrl("/sitemap.xml", base)}
- Robots: ${absoluteUrl("/robots.txt", base)}
- This file: ${absoluteUrl("/llms.txt", base)}

## Publishing rules

- Only \`published\` articles are public. Drafts and hidden (archived) pieces must not be cited as live.
- Slugs are Unicode-safe; percent-decode before fetching.
- Prefer the canonical URL in each article's JSON-LD over any syndicated copy.

## Optional

- Studio, dashboard, login and register are private authoring surfaces — skip them.
`;

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
