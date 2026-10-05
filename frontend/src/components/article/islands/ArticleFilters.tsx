import Link from "next/link";
import { Search, ArrowRight } from "lucide-react";

/** Native GET keeps searches shareable and works before hydration. */
export function ArticleFilters({
  categories,
  activeCategory,
  query,
}: {
  categories: { slug: string; name: string }[];
  activeCategory: string;
  query: string;
}) {
  const categoryHref = (slug: string) => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (slug) params.set("category", slug);
    return params.size ? `/articles?${params}` : "/articles";
  };
  return (
    <div className="sl-filters">
      <form action="/articles" method="get" role="search" className="sl-search">
        <Search size={19} aria-hidden="true" />
        <label htmlFor="article-search" className="sr-only">
          Search articles
        </label>
        <input
          key={query}
          id="article-search"
          name="q"
          type="search"
          defaultValue={query}
          placeholder="A topic, a question, a little curiosity…"
        />
        {activeCategory && (
          <input type="hidden" name="category" value={activeCategory} />
        )}
        <button type="submit" className="sl-button sl-button-small">
          Search
          <ArrowRight size={15} />
        </button>
      </form>
      <nav className="sl-filter-chips" aria-label="Filter articles by category">
        <Link
          href={categoryHref("")}
          aria-current={!activeCategory ? "page" : undefined}
        >
          All stories
        </Link>
        {categories.map((category) => (
          <Link
            key={category.slug}
            href={categoryHref(category.slug)}
            aria-current={activeCategory === category.slug ? "page" : undefined}
          >
            {category.name}
          </Link>
        ))}
        {(query || activeCategory) && (
          <Link href="/articles" className="sl-reset">
            Clear filters ×
          </Link>
        )}
      </nav>
    </div>
  );
}
