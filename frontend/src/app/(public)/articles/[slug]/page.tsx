import type { Metadata } from "next";
import Link from "next/link";

import { AnnotationAppendix } from "@/components/article/annotations/AnnotationAppendix";
import { AnnotationProvider } from "@/components/article/annotations/AnnotationProvider";
import { ReadingTracker } from "@/components/article/ReadingTracker";
import { ServerBlockRenderer } from "@/components/article/ServerBlockRenderer";
import { JsonLd } from "@/components/seo/JsonLd";
import { getAllSlugs, getArticle, getSite } from "@/lib/api.server";
import { normalizeMediaUrl } from "@/lib/media";
import { collectArticleSchemas } from "@/lib/schema";
import { normalizeSlug } from "@/lib/slug";

/**
 * Article detail -- the page that matters most for search.
 *
 * Previously `"use client"` with a useEffect fetch, so the title, body, author
 * and dates existed only after hydration and a crawler's first paint was a
 * skeleton. Now fully server-rendered with ISR.
 */

export const revalidate = 3600;
/** Slugs not in generateStaticParams still render on demand, then cache. */
export const dynamicParams = true;

export async function generateStaticParams() {
  try {
    const slugs = await getAllSlugs();
    // Prerender the most recent 500; the long tail renders on first request.
    // Slugs are returned DECODED -- Next percent-encodes when building paths,
    // and pre-encoding here would double-encode Bengali slugs into 404s.
    return slugs.slice(0, 500).map((entry) => ({ slug: entry.slug }));
  } catch {
    // A build must not fail because the API was briefly unreachable.
    return [];
  }
}

/**
 * Next 15 made `params` a Promise (and Next 16 removed the sync fallback), so
 * it must be awaited before `normalizeSlug` sees it -- reading `.slug` off the
 * promise yields `undefined`, which here would mean every article 404s.
 */
type RouteParams = { params: Promise<{ slug: string }> };

export async function generateMetadata({
  params,
}: RouteParams): Promise<Metadata> {
  const slug = normalizeSlug((await params).slug);

  let article;
  try {
    article = await getArticle(slug);
  } catch {
    return { title: "Article not found", robots: { index: false, follow: false } };
  }

  const { seo } = article;

  return {
    title: seo.meta_title,
    description: seo.meta_description,
    alternates: {
      canonical: seo.canonical_url,
      // `languages` becomes the <link rel="alternate" hreflang="..."> set.
      // The backend includes this article in its own alternates, because a
      // self-referential set is what search engines require -- listing only
      // the *other* languages reads as the obvious thing to do and silently
      // disables the whole cluster.
      ...(article.alternates && article.alternates.length > 1
        ? {
            languages: Object.fromEntries(
              article.alternates.map((entry) => [entry.locale, entry.url]),
            ),
          }
        : {}),
    },
    robots: {
      index: seo.robots_index,
      follow: seo.robots_follow,
      nocache: seo.robots_noarchive,
      googleBot: {
        index: seo.robots_index,
        follow: seo.robots_follow,
        noimageindex: seo.robots_noimageindex,
        "max-snippet": seo.max_snippet,
        "max-image-preview": seo.max_image_preview,
        "max-video-preview": seo.max_video_preview,
      },
    },
    openGraph: {
      type: "article",
      title: seo.og_title,
      description: seo.og_description,
      url: seo.canonical_url,
      siteName: article.site.name,
      locale: seo.og_locale || article.locale,
      publishedTime: article.published_at ?? undefined,
      modifiedTime: article.updated_at,
      authors: [article.author.name],
      section: article.category?.name,
      images: seo.og_image
        ? [{ url: seo.og_image, width: 1200, height: 630, alt: seo.og_image_alt || article.title }]
        : article.featured_image
          ? [{ url: article.featured_image, width: 1200, height: 630, alt: article.title }]
          : undefined,
    },
    twitter: {
      card: seo.twitter_card,
      title: seo.twitter_title,
      description: seo.twitter_description,
      images: seo.twitter_image ? [seo.twitter_image] : undefined,
      site: seo.twitter_site || undefined,
    },
  };
}

export default async function ArticlePage({ params }: RouteParams) {
  const slug = normalizeSlug((await params).slug);
  // Parallel: neither depends on the other.
  const [article, site] = await Promise.all([getArticle(slug), getSite()]);

  const publishedLabel = article.published_at
    ? new Date(article.published_at).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  return (
    <>
      <JsonLd data={collectArticleSchemas(article, site)} />
      <ReadingTracker articleId={article.id} />

      <article className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <header className="mb-8">
          <Link
            href="/articles"
            className="mb-6 inline-flex items-center gap-1 text-sm text-slate-500 transition hover:text-primary-600 dark:text-slate-400"
          >
            ← Back to articles
          </Link>

          {article.category && (
            <nav aria-label="Breadcrumb" className="mb-4 flex flex-wrap gap-2 text-sm">
              <Link
                href={`/categories/${encodeURIComponent(article.category.slug)}`}
                className="rounded-full bg-primary-50 px-3 py-1 font-medium text-primary-700 transition hover:bg-primary-100 dark:bg-primary-900/30 dark:text-primary-300"
              >
                {article.category.name}
              </Link>
            </nav>
          )}

          <h1 className="font-display text-3xl font-bold leading-tight text-slate-900 sm:text-4xl lg:text-5xl dark:text-slate-50">
            {article.title}
          </h1>

          {article.excerpt && (
            <p className="mt-4 text-lg text-slate-600 dark:text-slate-300">
              {article.excerpt}
            </p>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
            <span className="font-medium text-slate-700 dark:text-slate-200">
              {article.author.name}
            </span>
            {publishedLabel && article.published_at && (
              <>
                <span aria-hidden="true">·</span>
                {/* Machine-readable date for structured data and crawlers. */}
                <time dateTime={article.published_at}>{publishedLabel}</time>
              </>
            )}
            <span aria-hidden="true">·</span>
            <span>{article.reading_time} min read</span>
          </div>
        </header>

        {article.featured_image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={normalizeMediaUrl(article.featured_image)}
            alt={article.seo.og_image_alt || article.title}
            className="mb-10 w-full rounded-2xl"
            width={1200}
            height={630}
            // The LCP element: never lazy-loaded.
            fetchPriority="high"
          />
        )}

        <AnnotationProvider annotations={article.annotations_index}>
          <ServerBlockRenderer
            blocks={article.content?.blocks ?? []}
            annotations={article.annotations_index}
          />
          <AnnotationAppendix annotations={article.annotations_index} />
        </AnnotationProvider>
      </article>
    </>
  );
}
