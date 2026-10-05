/**
 * Types for the public delivery API (`/api/v1/public/`).
 *
 * Kept separate from `types.ts` (which describes the legacy `/api/*` surface)
 * so the two can diverge without one breaking the other.
 */

export interface ResolvedSEO {
  meta_title: string;
  meta_description: string;
  canonical_url: string;
  focus_keyword: string;
  secondary_keywords: string[];

  robots_index: boolean;
  robots_follow: boolean;
  robots_noarchive: boolean;
  robots_nosnippet: boolean;
  robots_noimageindex: boolean;
  max_snippet: number;
  max_image_preview: "none" | "standard" | "large";
  max_video_preview: number;
  unavailable_after: string | null;

  og_title: string;
  og_description: string;
  og_image: string;
  og_image_alt: string;
  og_type: string;
  og_locale: string;

  twitter_card: "summary" | "summary_large_image" | "player";
  twitter_title: string;
  twitter_description: string;
  twitter_image: string;
  twitter_site: string;

  schema_type: "Article" | "BlogPosting" | "NewsArticle" | "HowTo";
  structured_data_overrides: Record<string, unknown>;
  faq_items: { q: string; a: string }[];
  hide_from_sitemap: boolean;
  sitemap_priority: number;
  sitemap_changefreq: string;
}

export interface PublicAuthor {
  id: number;
  name: string;
  username: string;
  avatar: string | null;
}

export interface PublicCategory {
  id: number;
  name: string;
  slug: string;
  description: string;
  order: number;
  /** Categories are a tree; `subcategories` is gone with the flat model. */
  parent: number | null;
  /** Full slug path from the root, e.g. "technology/machine-learning". */
  url_path: string;
  depth: number;
  article_count?: number;
}

export interface PublicTag {
  id: number;
  name: string;
  slug: string;
  kind: string;
  description: string;
  usage_count: number;
}

/** One entry of the server-computed annotation index. */
export interface AnnotationEntry {
  id: string;
  block_id: string;
  block_type: string;
  kind: "text" | "image" | "audio" | "video" | "youtube" | "hotspot" | "chapter";
  /** The highlighted phrase this note is attached to. */
  label: string;
  title: string;
  /** Sanitized rich HTML. */
  html: string;
  plain: string;
  media: { url: string; type: string; alt: string } | null;
  time: number | null;
}

export interface EditorBlock {
  id?: string;
  type: string;
  data: Record<string, unknown>;
}

export interface PublicArticleListItem {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  url: string;
  canonical_url: string;
  featured_image: string;
  reading_time: number;
  word_count: number;
  locale: string;
  is_featured: boolean;
  published_at: string | null;
  updated_at: string;
  author: PublicAuthor;
  category: PublicCategory | null;
}

export interface PublicArticle extends PublicArticleListItem {
  content: { blocks: EditorBlock[]; time?: number; version?: string };
  seo: ResolvedSEO;
  /** Root-to-leaf trail, derived from the category tree. */
  category_path: { id: number; name: string; slug: string; url_path: string }[];
  tags: Array<{ name: string; slug: string; kind: string }>;
  /** hreflang set, including this article itself and an `x-default`. */
  alternates: Array<{ locale: string; url: string; is_current: boolean }>;
  annotations_index: AnnotationEntry[];
  site: { slug: string; name: string; base_url: string; locale: string };
}

/** Cursor-paginated: no `count`, and `next` is opaque. */
export interface CursorPage<T> {
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface SlugEntry {
  slug: string;
  updated_at: string;
  published_at: string | null;
}

export interface SiteConfig {
  name: string;
  slug: string;
  base_url: string;
  locale: string;
  site_title: string;
  title_template: string;
  default_meta_description: string;
  default_og_image: string;
  organization_jsonld: Record<string, unknown>;
  robots_extra: string;
  google_site_verification: string;
  allow_ai_crawlers: boolean;
}

export interface RedirectRule {
  source_path: string;
  target_path: string;
  status_code: 301 | 302 | 307 | 308;
  is_regex: boolean;
}

export interface SitemapShard {
  n: number;
  count: number;
  lastmod: string | null;
}

export interface SitemapEntry {
  url: string;
  lastmod: string | null;
  changefreq: string;
  priority: number;
  image: string | null;
}
