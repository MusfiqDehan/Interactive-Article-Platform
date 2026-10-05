/**
 * JSON-LD builders.
 *
 * Pure functions so they can be unit-tested without rendering. Every builder
 * deep-merges `seo.structured_data_overrides` **last**, so an editor can patch
 * any field from the studio without a code change.
 */

import type {
  PublicArticle,
  PublicArticleListItem,
  SiteConfig,
} from "./public-types";

/** Google truncates headlines around 110 characters. */
const HEADLINE_MAX = 110;

type Json = Record<string, unknown>;

export function deepMerge(base: Json, override: Json): Json {
  const out: Json = { ...base };
  for (const [key, value] of Object.entries(override || {})) {
    const existing = out[key];
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      existing &&
      typeof existing === "object" &&
      !Array.isArray(existing)
    ) {
      out[key] = deepMerge(existing as Json, value as Json);
    } else {
      out[key] = value;
    }
  }
  return out;
}

function truncate(text: string, max: number): string {
  const trimmed = (text || "").trim();
  return trimmed.length <= max ? trimmed : `${trimmed.slice(0, max - 1).trimEnd()}…`;
}

export function articleSchema(article: PublicArticle, site: SiteConfig): Json {
  const { seo } = article;

  const base: Json = {
    "@context": "https://schema.org",
    "@type": seo.schema_type || "Article",
    headline: truncate(seo.meta_title || article.title, HEADLINE_MAX),
    description: seo.meta_description,
    inLanguage: article.locale,
    wordCount: article.word_count,
    isAccessibleForFree: true,
    mainEntityOfPage: { "@type": "WebPage", "@id": seo.canonical_url },
    url: article.url,
    datePublished: article.published_at,
    dateModified: article.updated_at,
    author: {
      "@type": "Person",
      name: article.author?.name,
      url: `${site.base_url}/authors/${article.author?.username}`,
    },
    publisher: {
      "@type": "Organization",
      name: site.name,
      url: site.base_url,
    },
  };

  if (seo.og_image) {
    base.image = [seo.og_image];
  }
  if (article.category) {
    base.articleSection = article.category.name;
  }
  if (seo.focus_keyword || seo.secondary_keywords?.length) {
    base.keywords = [seo.focus_keyword, ...(seo.secondary_keywords || [])]
      .filter(Boolean)
      .join(", ");
  }

  return deepMerge(base, seo.structured_data_overrides || {});
}

export function breadcrumbSchema(article: PublicArticle, site: SiteConfig): Json | null {
  const trail = article.category_path || [];
  if (trail.length === 0) return null;

  const items = [
    { name: "Home", url: site.base_url },
    { name: "Articles", url: `${site.base_url}/articles` },
    ...trail.map((entry) => ({
      name: entry.name,
      url: `${site.base_url}/categories/${encodeURIComponent(entry.slug)}`,
    })),
    { name: article.title, url: article.url },
  ];

  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

export function organizationSchema(site: SiteConfig): Json {
  return deepMerge(
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      name: site.name,
      url: site.base_url,
      logo: site.default_og_image || `${site.base_url}/logo.svg`,
    },
    (site.organization_jsonld as Json) || {},
  );
}

export function websiteSchema(site: SiteConfig): Json {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: site.site_title || site.name,
    url: site.base_url,
    inLanguage: site.locale,
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${site.base_url}/search?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };
}

/**
 * FAQPage from explicit faq_items plus question-shaped annotations.
 *
 * An annotation whose title ends in "?" is, structurally, a question with an
 * answer -- worth surfacing as a rich result rather than leaving buried.
 */
export function faqSchema(article: PublicArticle): Json | null {
  const explicit = (article.seo.faq_items || []).filter((f) => f.q && f.a);
  const fromAnnotations = (article.annotations_index || [])
    .filter((a) => a.title?.trim().endsWith("?") && a.plain)
    .map((a) => ({ q: a.title, a: a.plain }));

  const all = [...explicit, ...fromAnnotations];
  if (all.length === 0) return null;

  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: all.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
}

/**
 * DefinedTermSet from glossary-style annotations.
 *
 * Each note becomes a term with a deep link to its `#annotation-<id>` anchor,
 * which is only possible because the appendix renders server-side.
 */
export function definedTermSetSchema(article: PublicArticle): Json | null {
  const terms = (article.annotations_index || []).filter(
    (a) => a.id && a.label && a.plain && !a.title?.trim().endsWith("?"),
  );
  if (terms.length === 0) return null;

  return {
    "@context": "https://schema.org",
    "@type": "DefinedTermSet",
    name: `Notes for ${article.title}`,
    hasDefinedTerm: terms.map((term) => ({
      "@type": "DefinedTerm",
      name: term.label || term.title,
      description: term.plain,
      url: `${article.url}#annotation-${term.id}`,
    })),
  };
}

export function collectArticleSchemas(
  article: PublicArticle,
  site: SiteConfig,
): Json[] {
  return [
    articleSchema(article, site),
    breadcrumbSchema(article, site),
    faqSchema(article),
    definedTermSetSchema(article),
  ].filter((schema): schema is Json => schema !== null);
}

export function articleListSchema(
  articles: PublicArticleListItem[],
  site: SiteConfig,
  name: string,
): Json {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name,
    itemListElement: articles.map((article, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: article.url,
      name: article.title,
    })),
  };
}
