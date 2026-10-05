import type { Metadata } from "next";
import Link from "next/link";

import { ArticleCard } from "@/components/article/ArticleCard";
import { getCategory, listArticles } from "@/lib/api.server";
import { normalizeSlug } from "@/lib/slug";

/**
 * Rendered per request, deliberately -- no `generateStaticParams` here.
 *
 * This route paginates with a `?cursor=` token, and reading a search param is
 * fundamentally incompatible with prerendering: the prerender has no request to
 * read it from. Next 14 resolved that contradiction silently by prerendering the
 * page and handing the component an empty `searchParams`, so **every cursor was
 * ignored and page 2 of a category served page 1**. Next 16 raises
 * DYNAMIC_SERVER_USAGE instead, which is how the bug surfaced.
 *
 * Dynamic rendering is cheap here because both reads below are served from the
 * fetch cache (category 1h, listing 5m), so a request is a cache hit plus a
 * render rather than an API round trip. The article detail route, which has no
 * search params, keeps full static generation.
 */
export const dynamic = "force-dynamic";

/** Next 15+ passes both as Promises; Next 16 dropped the sync fallback. */
type RouteProps = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ cursor?: string }>;
};

export async function generateMetadata({
  params,
}: Pick<RouteProps, "params">): Promise<Metadata> {
  try {
    const category = await getCategory(normalizeSlug((await params).slug));
    return {
      title: category.name,
      description:
        category.description || `Articles filed under ${category.name}.`,
    };
  } catch {
    return { title: "Category not found", robots: { index: false } };
  }
}

export default async function CategoryPage({
  params,
  searchParams,
}: RouteProps) {
  const [{ slug: rawSlug }, { cursor }] = await Promise.all([
    params,
    searchParams,
  ]);
  const slug = normalizeSlug(rawSlug);
  const [category, page] = await Promise.all([
    getCategory(slug),
    listArticles({ category: slug, cursor, page_size: 9 }),
  ]);

  const nextToken = page.next
    ? new URL(page.next).searchParams.get("cursor")
    : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-6 text-sm text-slate-500">
        <Link href="/categories" className="hover:text-primary-600">
          Categories
        </Link>
        <span className="mx-2" aria-hidden="true">
          /
        </span>
        <span className="text-slate-700 dark:text-slate-300">{category.name}</span>
      </nav>

      <header className="mb-8">
        <h1 className="font-display text-3xl font-bold text-slate-900 sm:text-4xl dark:text-slate-50">
          {category.name}
        </h1>
        {category.description && (
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            {category.description}
          </p>
        )}
      </header>

      {page.results.length === 0 ? (
        <p className="py-16 text-center text-slate-500">
          No articles in this category yet.
        </p>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {page.results.map((article, index) => (
            <ArticleCard key={article.id} article={article} priority={index === 0} />
          ))}
        </div>
      )}

      {nextToken && (
        <nav className="mt-10 flex justify-center" aria-label="Pagination">
          <Link
            href={`/categories/${encodeURIComponent(slug)}?cursor=${encodeURIComponent(nextToken)}`}
            className="btn-secondary"
            rel="next"
          >
            Next
          </Link>
        </nav>
      )}
    </div>
  );
}
