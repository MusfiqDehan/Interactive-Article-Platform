import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { PageIntro, EmptyState } from "@/components/storyloom/Primitives";

import { ArticleCard } from "@/components/article/ArticleCard";
import { ArticleFilters } from "@/components/article/islands/ArticleFilters";
import { JsonLd } from "@/components/seo/JsonLd";
import {
  CmsError,
  getCategoriesSafe,
  getSiteSafe,
  listArticles,
} from "@/lib/api.server";
import { articleListSchema } from "@/lib/schema";
import { absoluteUrl, socialMetadata } from "@/lib/seo";

/**
 * Article index.
 *
 * Server-rendered, with filters driven by `searchParams` rather than component
 * state. That matters for more than SSR: the previous version paginated with
 * `<button>` elements, so pages 2+ had no crawlable URL at all and every
 * article past the first page was unreachable to a crawler.
 */

export const revalidate = 300;

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteSafe();
  const title = "Articles";
  const description = `Browse every published article on ${site.site_title || site.name}.`;
  const url = absoluteUrl("/articles", site.base_url);
  const image = site.default_og_image || "/og/platform.jpg";
  return {
    title,
    description,
    alternates: { canonical: url },
    ...socialMetadata({
      title: `${title} | ${site.site_title || site.name}`,
      description,
      url,
      image,
      imageAlt: description,
      locale: site.locale,
      siteName: site.name,
    }),
  };
}

type SearchParams = {
  q?: string;
  category?: string;
  cursor?: string;
};

export default async function ArticlesPage({
  searchParams,
}: {
  // Next 15+ delivers this as a Promise; awaiting it is what makes the route
  // dynamic at the point of access rather than for the whole segment.
  searchParams: Promise<SearchParams>;
}) {
  const query = await searchParams;

  const [page, categories, site] = await Promise.all([
    listArticles({
      q: query.q,
      category: query.category,
      cursor: query.cursor,
      page_size: 9,
    }).catch((error: unknown) => {
      if (error instanceof CmsError || error instanceof TypeError) return null;
      throw error;
    }),
    getCategoriesSafe(),
    getSiteSafe(),
  ]);

  const buildHref = (cursor: string | null) => {
    if (!cursor) return null;
    const params = new URLSearchParams();
    if (query.q) params.set("q", query.q);
    if (query.category) params.set("category", query.category);
    // The API returns absolute cursor URLs; keep only the opaque token.
    const token = new URL(cursor, site.base_url).searchParams.get("cursor");
    if (token) params.set("cursor", token);
    return `/articles?${params.toString()}`;
  };

  const nextHref = buildHref(page?.next ?? null);
  const prevHref = buildHref(page?.previous ?? null);

  return (
    <>
      {page && (
        <JsonLd data={articleListSchema(page.results, site, "Articles")} />
      )}

      <div className="sl-container sl-listing">
        <PageIntro
          eyebrow="THE STORYLOOM COLLECTION"
          title="Good stories."
          accent="Deeper discoveries."
          description="Ideas worth your time. Perspectives worth exploring. Find your next read and discover what lies beneath the surface."
        >
          <Link href="/categories" className="sl-text-link">
            Explore by topic <ArrowRight size={16} />
          </Link>
        </PageIntro>

        <ArticleFilters
          categories={categories.map((c) => ({ slug: c.slug, name: c.name }))}
          activeCategory={query.category ?? ""}
          query={query.q ?? ""}
        />

        {!page ? (
          <EmptyState
            title="The collection is temporarily unavailable."
            description="We couldn’t load the articles. Please try again in a moment."
            href="/articles"
            action="Try again"
          />
        ) : page.results.length === 0 ? (
          <EmptyState
            title={
              query.q || query.category
                ? "No stories found. Keep exploring."
                : "The next chapter is on its way."
            }
            description={
              query.q || query.category
                ? "Try another search or clear your filters to discover something new."
                : "Published stories will appear here. Come back soon for a fresh perspective."
            }
            href={query.q || query.category ? "/articles" : "/categories"}
            action={
              query.q || query.category ? "Clear filters" : "Explore topics"
            }
          />
        ) : (
          <div className="sl-article-grid">
            {page.results.map((article, index) => (
              <ArticleCard
                key={article.id}
                article={article}
                priority={index === 0}
              />
            ))}
          </div>
        )}

        {/* Real links, so pagination is crawlable and shareable. */}
        {(nextHref || prevHref) && (
          <nav className="sl-pagination" aria-label="Pagination">
            {prevHref ? (
              <Link
                href={prevHref}
                className="sl-button sl-button-outline"
                rel="prev"
              >
                <ArrowLeft size={16} /> Previous
              </Link>
            ) : null}
            {nextHref ? (
              <Link
                href={nextHref}
                className="sl-button sl-button-outline"
                rel="next"
              >
                Next <ArrowRight size={16} />
              </Link>
            ) : null}
          </nav>
        )}
      </div>
    </>
  );
}
