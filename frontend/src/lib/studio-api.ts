"use client";

import axios, { type AxiosInstance } from "axios";

import { publicEnvFromWindow } from "./runtime-config";

/**
 * Client for `/api/v1/studio/`.
 *
 * Separate instance from `lib/api.ts` (which now serves auth only) because the
 * two have different base URLs and different failure semantics -- the studio
 * needs the raw 409 body to drive conflict resolution, which the other
 * client's interceptors would flatten. Token storage is shared, so one login
 * covers both.
 */

function studioBaseUrl(): string {
  const base =
    publicEnvFromWindow()?.apiBase ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://localhost:8003/api";
  return `${base.replace(/\/$/, "")}/v1/studio`;
}

function createClient(): AxiosInstance {
  const client = axios.create({
    baseURL: studioBaseUrl(),
    headers: { "Content-Type": "application/json" },
  });

  client.interceptors.request.use((config) => {
    if (typeof window !== "undefined") {
      const raw = localStorage.getItem("tokens");
      if (raw) {
        try {
          const { access } = JSON.parse(raw);
          if (access) config.headers.Authorization = `Bearer ${access}`;
        } catch {
          /* corrupt storage is handled by the 401 path below */
        }
      }
      // Tells the backend which tenant this request is for; it is validated
      // against the user's SiteMembership, so it cannot be used to reach a site
      // the user has no access to.
      const site = localStorage.getItem("studio-site");
      if (site) config.headers["X-CMS-Site"] = site;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const original = error.config;
      // 409 is a normal, expected outcome here (stale content, illegal
      // transition). It must reach the caller intact rather than being retried
      // or redirected -- the body is what the conflict UI renders.
      if (error.response?.status !== 401 || original?._retry) {
        return Promise.reject(error);
      }

      original._retry = true;
      try {
        const raw = localStorage.getItem("tokens");
        if (!raw) throw new Error("no tokens");
        const { refresh } = JSON.parse(raw);
        const base = studioBaseUrl().replace(/\/v1\/studio$/, "");
        const { data } = await axios.post(`${base}/auth/token/refresh/`, { refresh });
        const tokens = { access: data.access, refresh: data.refresh || refresh };
        localStorage.setItem("tokens", JSON.stringify(tokens));
        original.headers.Authorization = `Bearer ${tokens.access}`;
        return client(original);
      } catch {
        localStorage.removeItem("tokens");
        localStorage.removeItem("user");
        if (typeof window !== "undefined") window.location.href = "/login";
        return Promise.reject(error);
      }
    },
  );

  return client;
}

let instance: AxiosInstance | null = null;

/** Lazily built so runtime config is read after hydration, not at import. */
export function studioApi(): AxiosInstance {
  if (!instance) instance = createClient();
  return instance;
}

// -- typed helpers ----------------------------------------------------------

export type StudioStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "scheduled"
  | "published"
  | "archived";

export interface AvailableTransition {
  name: string;
  label: string;
  target: StudioStatus;
}

export interface StudioArticleRow {
  id: number;
  title: string;
  slug: string;
  status: StudioStatus;
  is_live: boolean;
  is_featured: boolean;
  word_count: number;
  views_count: number;
  reading_time: number;
  excerpt: string;
  featured_image: string;
  author: { id: number; name: string; email: string } | null;
  category: number | null;
  category_name?: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  placement_count?: number;
}

export interface StudioArticle extends StudioArticleRow {
  content: { blocks: unknown[] };
  tags: Array<{ id: number; name: string; slug: string; kind: string }>;
  /** Write-only: names or slugs; unknown ones are created server-side. */
  tag_slugs?: string[];
  content_hash: string;
  scheduled_publish_at: string | null;
  scheduled_unpublish_at: string | null;
  last_published_at: string | null;
  locale: string;
  available_transitions: AvailableTransition[];
  placements: Array<{
    id: number;
    site_slug: string;
    site_name: string;
    is_primary: boolean;
    is_live: boolean;
    url: string;
  }>;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface RevisionRow {
  id: number;
  number: number;
  status: string;
  content_hash: string;
  created_at: string;
  created_by_name: string;
  reason: string;
  is_autosave: boolean;
  summary: { title: string; blocks: number };
}

/** Raised when the server reports the article moved under us (HTTP 409). */
export class StaleContentError extends Error {
  constructor(
    readonly currentVersion: string,
    readonly yourVersion: string,
    readonly modifiedAt: string | null,
  ) {
    super("This article was modified by someone else.");
    this.name = "StaleContentError";
  }
}

export async function listArticles(params: Record<string, string | number | undefined>) {
  const { data } = await studioApi().get<Paginated<StudioArticleRow>>("/articles/", {
    params,
  });
  return data;
}

export async function getArticle(slug: string) {
  const { data } = await studioApi().get<StudioArticle>(
    `/articles/${encodeURIComponent(slug)}/`,
  );
  return data;
}

/**
 * Save an article, sending the version it was loaded at.
 *
 * Throws `StaleContentError` on 409 so callers can offer keep-mine / take-
 * theirs rather than discovering the clobber later.
 */
export async function saveArticle(
  slug: string,
  patch: Partial<StudioArticle>,
  baseVersion?: string,
) {
  try {
    const { data } = await studioApi().patch<StudioArticle>(
      `/articles/${encodeURIComponent(slug)}/`,
      patch,
      baseVersion ? { headers: { "If-Match": `"${baseVersion}"` } } : undefined,
    );
    return data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      const body = error.response.data ?? {};
      if (body.code === "stale_content") {
        throw new StaleContentError(
          body.current_version ?? "",
          body.your_version ?? "",
          body.modified_at ?? null,
        );
      }
    }
    throw error;
  }
}

export async function createArticle(patch: Partial<StudioArticle>) {
  const { data } = await studioApi().post<StudioArticle>("/articles/", patch);
  return data;
}

export async function runTransition(
  slug: string,
  transition: string,
  extra: { reason?: string; scheduled_publish_at?: string } = {},
) {
  const { data } = await studioApi().post<{
    article: StudioArticle;
    available_transitions: AvailableTransition[];
  }>(`/articles/${encodeURIComponent(slug)}/transition/`, { transition, ...extra });
  return data;
}

export async function listRevisions(slug: string) {
  const { data } = await studioApi().get<Paginated<RevisionRow> | RevisionRow[]>(
    `/articles/${encodeURIComponent(slug)}/revisions/`,
  );
  return Array.isArray(data) ? data : data.results;
}

export async function restoreRevision(slug: string, number: number) {
  const { data } = await studioApi().post<StudioArticle>(
    `/articles/${encodeURIComponent(slug)}/revisions/${number}/restore/`,
  );
  return data;
}

export interface BulkResultRow {
  slug: string;
  ok: boolean;
  /** Stable key: "ok" | "not_found" | "forbidden" | "illegal". */
  code: string;
  detail: string;
  status?: StudioStatus;
}

export interface BulkResult {
  requested: number;
  succeeded: number;
  failed: number;
  results: BulkResultRow[];
}

/**
 * Run one transition across many articles.
 *
 * Resolves on partial failure rather than rejecting -- the server reports each
 * article individually and a 200 with `failed > 0` is the expected shape, not
 * an error to catch.
 */
export async function bulkTransition(
  slugs: string[],
  transition: string,
  reason = "",
) {
  const { data } = await studioApi().post<BulkResult>("/articles/bulk-transition/", {
    slugs,
    transition,
    reason,
  });
  return data;
}

/**
 * Permanently delete many articles.
 *
 * Same per-row result shape as `bulkTransition`. Hide (`archive`) is the
 * reversible bulk action; this removes the rows.
 */
export async function bulkDelete(slugs: string[], reason = "") {
  const { data } = await studioApi().post<BulkResult>("/articles/bulk-delete/", {
    slugs,
    reason,
  });
  return data;
}

export interface CategoryRow {
  id: number;
  name: string;
  slug: string;
  description: string;
  is_active: boolean;
  order: number;
  parent: number | null;
  path: string;
  url_path: string;
  depth: number;
  child_count?: number;
  article_count?: number;
}

export interface CategoryNode extends CategoryRow {
  children: CategoryNode[];
}

export async function listCategories() {
  const { data } = await studioApi().get<Paginated<CategoryRow>>("/categories/", {
    params: { page_size: 200 },
  });
  return data.results ?? [];
}

export async function getCategoryTree() {
  const { data } = await studioApi().get<CategoryNode[]>("/categories/tree/");
  return data;
}

export interface MovedPath {
  id: number;
  name: string;
  from: string;
  to: string;
}

/**
 * Reparent a category.
 *
 * Returns the URLs that changed as a side effect, because they are the whole
 * reason a move is risky: every one of them is a live address that just started
 * 404ing, and the only moment anyone knows the old value is right now.
 */
export async function moveCategory(slug: string, parent: number | null, order?: number) {
  const { data } = await studioApi().post<{
    category: CategoryRow;
    changed_paths: MovedPath[];
  }>(`/categories/${encodeURIComponent(slug)}/move/`, { parent, order });
  return data;
}

export async function saveCategory(slug: string | null, patch: Partial<CategoryRow>) {
  const client = studioApi();
  const { data } = slug
    ? await client.patch<CategoryRow>(`/categories/${encodeURIComponent(slug)}/`, patch)
    : await client.post<CategoryRow>("/categories/", patch);
  return data;
}

export interface TagRow {
  id: number;
  name: string;
  slug: string;
  kind: "topic" | "series" | "format";
  description: string;
  usage_count: number;
  is_active: boolean;
}

export async function listTags(params: Record<string, string | number> = {}) {
  const { data } = await studioApi().get<Paginated<TagRow>>("/tags/", {
    params: { page_size: 200, ...params },
  });
  return data;
}

export async function saveTag(slug: string | null, patch: Partial<TagRow>) {
  const client = studioApi();
  const { data } = slug
    ? await client.patch<TagRow>(`/tags/${encodeURIComponent(slug)}/`, patch)
    : await client.post<TagRow>("/tags/", patch);
  return data;
}

export async function mergeTags(into: string, sources: string[]) {
  const { data } = await studioApi().post<{
    into: TagRow;
    merged: string[];
    items_moved: number;
    skipped: Array<{ slug: string; reason: string }>;
  }>("/tags/merge/", { into, sources });
  return data;
}

export interface ReviewAssignment {
  id: number;
  article: number;
  article_title?: string;
  assignee: number;
  assignee_name?: string;
  assigned_by_name?: string;
  state: "pending" | "approved" | "changes_requested" | "cancelled";
  note: string;
  created_at: string;
  resolved_at: string | null;
}

export async function listReviewInbox(params: Record<string, string> = {}) {
  const { data } = await studioApi().get<Paginated<StudioArticleRow>>("/review-inbox/", {
    params,
  });
  return data;
}

export async function listReviews(scope: string) {
  const { data } = await studioApi().get<Paginated<ReviewAssignment>>("/reviews/", {
    params: { scope },
  });
  return data;
}

export async function resolveReview(id: number, state: string) {
  const { data } = await studioApi().post<ReviewAssignment>(`/reviews/${id}/resolve/`, {
    state,
  });
  return data;
}

export interface RedirectRow {
  id: number;
  source_path: string;
  target_path: string;
  status_code: 301 | 302 | 307 | 308;
  is_regex: boolean;
  is_active: boolean;
  hit_count: number;
  last_hit_at: string | null;
  note: string;
  created_at: string;
}

export async function listRedirects(params: Record<string, string | number> = {}) {
  const { data } = await studioApi().get<Paginated<RedirectRow>>("/redirects/", {
    params: { page_size: 100, ...params },
  });
  return data;
}

export async function saveRedirect(id: number | null, patch: Partial<RedirectRow>) {
  const client = studioApi();
  const { data } = id
    ? await client.patch<RedirectRow>(`/redirects/${id}/`, patch)
    : await client.post<RedirectRow>("/redirects/", patch);
  return data;
}

export async function deleteRedirect(id: number) {
  await studioApi().delete(`/redirects/${id}/`);
}

export interface CalendarEntry {
  id: number;
  title: string;
  slug: string;
  status: StudioStatus;
  is_live: boolean;
  author_name: string;
  at: string | null;
  kind: "scheduled_publish" | "scheduled_unpublish" | "published";
  scheduled_publish_at: string | null;
  scheduled_unpublish_at: string | null;
  published_at: string | null;
}

export async function getCalendar(from: Date, to: Date) {
  const { data } = await studioApi().get<{
    entries: CalendarEntry[];
    unscheduled: CalendarEntry[];
  }>("/calendar/", {
    // toISOString() ends in "Z", so there is no "+" to be eaten by query-string
    // decoding on the way in.
    params: { from: from.toISOString(), to: to.toISOString() },
  });
  return data;
}

export async function scheduleArticle(
  slug: string,
  patch: { scheduled_publish_at?: string | null; scheduled_unpublish_at?: string | null },
) {
  const { data } = await studioApi().post<StudioArticle>(
    `/articles/${encodeURIComponent(slug)}/schedule/`,
    patch,
  );
  return data;
}

export interface SiteOption {
  id: number;
  name: string;
  slug: string;
  kind: string;
  primary_domain: string;
  base_url: string;
  locale: string;
  is_default: boolean;
  is_active: boolean;
}

export async function listSites() {
  const { data } = await studioApi().get<SiteOption[]>("/sites/");
  return data;
}

export interface Membership {
  id: number;
  user: { id: number; name: string; email: string; role: string; avatar?: string };
  role: "owner" | "editor" | "author" | "viewer";
  created_at: string;
}

export async function listPeople(params: Record<string, string> = {}) {
  const { data } = await studioApi().get<Paginated<Membership>>("/people/", { params });
  return data;
}

export async function invitePerson(email: string, role: string) {
  const { data } = await studioApi().post<Membership>("/people/", { email, role });
  return data;
}

export async function setPersonRole(id: number, role: string) {
  const { data } = await studioApi().patch<Membership>(`/people/${id}/`, { role });
  return data;
}

export async function removePerson(id: number) {
  await studioApi().delete(`/people/${id}/`);
}

export interface SiteSettings {
  site_title: string;
  title_template: string;
  default_meta_description: string;
  default_og_image: string;
  robots_extra: string;
  google_site_verification: string;
  allow_ai_crawlers: boolean;
  revalidate_url: string;
  analytics_snippet: string;
  organization_jsonld: Record<string, unknown>;
}

export async function getSettings() {
  const { data } = await studioApi().get<SiteSettings>("/settings/");
  return data;
}

export async function saveSettings(patch: Partial<SiteSettings>) {
  const { data } = await studioApi().patch<SiteSettings>("/settings/", patch);
  return data;
}

export interface ApiKeyRow {
  id: number;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
  /** Present only in the create response, and never again. */
  key?: string;
}

export async function listApiKeys() {
  const { data } = await studioApi().get<Paginated<ApiKeyRow>>("/api-keys/");
  return data.results ?? [];
}

export async function createApiKey(name: string, scopes: string[]) {
  const { data } = await studioApi().post<ApiKeyRow>("/api-keys/", { name, scopes });
  return data;
}

export async function revokeApiKey(id: number) {
  await studioApi().delete(`/api-keys/${id}/`);
}

export interface MediaRow {
  id: number;
  url: string;
  file: string;
  file_type: string;
  title: string;
  alt_text: string;
  file_size: number;
  mime_type: string;
  created_at: string;
}

export async function listMedia(params: Record<string, string | number> = {}) {
  const { data } = await studioApi().get<Paginated<MediaRow>>("/media/", {
    params: { page_size: 40, ...params },
  });
  return data;
}

export async function saveMedia(id: number, patch: Partial<MediaRow>) {
  const { data } = await studioApi().patch<MediaRow>(`/media/${id}/`, patch);
  return data;
}

export async function deleteMedia(id: number) {
  await studioApi().delete(`/media/${id}/`);
}

// -- distribution -----------------------------------------------------------

export interface Destination {
  id: number;
  name: string;
  kind: "site" | "partner_api" | "webhook" | "rss" | "newsletter";
  target_site: number | null;
  target_site_name: string | null;
  endpoint_url: string;
  headers: Record<string, string>;
  events: string[];
  is_active: boolean;
  is_deliverable: boolean;
  disabled_at: string | null;
  disabled_reason: string;
  consecutive_failures: number;
  has_secret: boolean;
  created_at: string;
  /** Present only in the create response, and never again. */
  secret?: string;
}

export type DeliveryState =
  | "pending"
  | "delivering"
  | "delivered"
  | "failed"
  | "abandoned"
  | "skipped";

export interface Delivery {
  id: number;
  destination: number;
  destination_name: string;
  article: number | null;
  article_label: string;
  event: string;
  state: DeliveryState;
  attempts: number;
  next_attempt_at: string | null;
  last_error: string;
  response_status: number | null;
  payload_snapshot: Record<string, unknown>;
  response_snapshot: Record<string, unknown>;
  is_retryable: boolean;
  event_id: string;
  created_at: string;
  delivered_at: string | null;
}

export async function listDestinations() {
  const { data } = await studioApi().get<Paginated<Destination>>("/destinations/", {
    params: { page_size: 100 },
  });
  return data.results ?? [];
}

export async function saveDestination(id: number | null, patch: Partial<Destination>) {
  const client = studioApi();
  const { data } = id
    ? await client.patch<Destination>(`/destinations/${id}/`, patch)
    : await client.post<Destination>("/destinations/", patch);
  return data;
}

export async function deleteDestination(id: number) {
  await studioApi().delete(`/destinations/${id}/`);
}

export async function enableDestination(id: number) {
  const { data } = await studioApi().post<Destination>(`/destinations/${id}/enable/`);
  return data;
}

export async function listDeliveries(params: Record<string, string | number> = {}) {
  const { data } = await studioApi().get<Paginated<Delivery>>("/deliveries/", {
    params: { page_size: 50, ...params },
  });
  return data;
}

export async function retryDelivery(id: number) {
  const { data } = await studioApi().post<Delivery>(`/deliveries/${id}/retry/`);
  return data;
}

// -- social -----------------------------------------------------------------

export type Platform = "x" | "linkedin" | "facebook" | "threads";

export interface PlatformSpec {
  key: Platform;
  label: string;
  max_length: number;
  /** Length a URL counts as, whatever its real length. X uses 23. */
  url_length: number | null;
  max_images: number;
  max_videos: number;
  max_image_bytes: number;
  max_video_bytes: number;
  image_mimes: string[];
  video_mimes: string[];
  aspect_ratio_range: [number, number];
  two_step_publish: boolean;
  supports_alt_text: boolean;
  max_hashtags: number;
  notes: string[];
}

export interface SocialAccount {
  id: number;
  platform: Platform;
  provider: string;
  display_name: string;
  handle: string;
  avatar_url: string;
  status: "connected" | "expired" | "revoked" | "error";
  status_detail: string;
  is_usable: boolean;
  last_used_at: string | null;
  capabilities: Record<string, boolean>;
}

export interface SocialTarget {
  id: number;
  account: number;
  account_name: string;
  platform: Platform;
  caption: string;
  media: Array<{ url: string; alt?: string; mime?: string; bytes?: number }>;
  state: "pending" | "publishing" | "retrying" | "published" | "failed" | "cancelled";
  attempts: number;
  last_error: string;
  external_url: string;
  metrics: Record<string, number | string | null>;
  published_at: string | null;
  next_attempt_at: string | null;
  counted_length: number;
  problems: string[];
}

export interface SocialPost {
  id: number;
  article: number | null;
  article_label: string;
  state: "draft" | "scheduled" | "publishing" | "published" | "partial" | "failed" | "cancelled";
  scheduled_at: string | null;
  targets: SocialTarget[];
  created_at: string;
}

export interface CaptionPreview {
  platform: Platform;
  caption: string;
  fits: boolean;
  counted_length: number;
  max_length: number;
}

export async function getPlatformSpecs() {
  const { data } = await studioApi().get<PlatformSpec[]>("/social/platform-specs/");
  return data;
}

export async function listSocialAccounts() {
  const { data } = await studioApi().get<Paginated<SocialAccount>>("/social/accounts/", {
    params: { page_size: 50 },
  });
  return data.results ?? [];
}

export async function deriveCaptions(body: {
  article?: number;
  platforms?: Platform[];
  template?: string;
  hashtags?: string[];
}) {
  const { data } = await studioApi().post<CaptionPreview[]>("/social/captions/", body);
  return data;
}

export async function listSocialPosts(params: Record<string, string | number> = {}) {
  const { data } = await studioApi().get<Paginated<SocialPost>>("/social/posts/", {
    params: { page_size: 25, ...params },
  });
  return data;
}

export async function createSocialPost(body: {
  article?: number | null;
  scheduled_at?: string | null;
  targets: Array<{ account: number; caption: string; media?: unknown[] }>;
}) {
  const { data } = await studioApi().post<SocialPost>("/social/posts/", body);
  return data;
}

export async function retrySocialTarget(id: number) {
  const { data } = await studioApi().post<SocialTarget>(`/social/targets/${id}/retry/`);
  return data;
}
