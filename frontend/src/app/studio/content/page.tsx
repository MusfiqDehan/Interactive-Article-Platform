"use client";

import { Filter, Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BulkActionDrawer } from "@/components/studio/BulkActionDrawer";
import { STATUS_OPTIONS, StatusBadge } from "@/components/studio/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import {
  listArticles,
  listCategories,
  type Paginated,
  type StudioArticleRow,
} from "@/lib/studio-api";

/**
 * Content list.
 *
 * **Every filter lives in the URL query string.** That is not a stylistic
 * choice: it is what makes a view shareable ("here are the drafts missing SEO"),
 * makes browser back/forward behave, and lets the saved-view tabs below be
 * nothing more than links. Holding filters in component state would have made
 * all three impossible.
 */

interface SavedView {
  key: string;
  label: string;
  query: Record<string, string>;
}

/**
 * Saved views as tabs. The single highest-leverage addition for an editorial
 * team -- "what needs my attention" is the question actually being asked, and
 * without these it takes three filter selections to answer.
 */
const SAVED_VIEWS: SavedView[] = [
  { key: "all", label: "All", query: {} },
  { key: "drafts", label: "Drafts", query: { status: "draft" } },
  { key: "review", label: "Needs review", query: { status: "in_review" } },
  { key: "scheduled", label: "Scheduled", query: { status: "scheduled" } },
  { key: "published", label: "Public", query: { status: "published" } },
  { key: "hidden", label: "Hidden", query: { status: "archived" } },
  { key: "mine", label: "My articles", query: { mine: "1" } },
];

const PAGE_SIZE = 25;

export default function ContentListPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  /**
   * The result is stored together with the query it answers.
   *
   * That pairing is what lets `loading` be *derived* (`result.key !== queryKey`)
   * rather than flipped with a synchronous `setState` at the top of the effect --
   * which React 19 flags, because it forces a second render pass on every fetch.
   * It also makes stale responses impossible to render: a reply for an
   * abandoned query simply never matches the current key.
   */
  const [result, setResult] = useState<{
    key: string;
    data?: Paginated<StudioArticleRow>;
    error?: string;
  }>({ key: "" });
  const [categories, setCategories] = useState<{ id: number; name: string }[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showFilters, setShowFilters] = useState(true);
  const [bulkOpen, setBulkOpen] = useState(false);
  /** Bumped to force a refetch after a bulk action changes states. */
  const [refreshToken, setRefreshToken] = useState(0);

  const params = useMemo(
    () => Object.fromEntries(searchParams.entries()),
    [searchParams],
  );

  /** Rewrite the query string; `null` removes a key. */
  const setParam = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value === null || value === "") next.delete(key);
        else next.set(key, value);
      }
      // Any filter change invalidates the page number -- staying on page 4 of a
      // now 1-page result set shows an empty table and looks like a bug.
      if (!("page" in patch)) next.delete("page");
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  const query = useMemo(() => {
    const built: Record<string, string | number> = {
      page_size: PAGE_SIZE,
      page: params.page || 1,
      ordering: params.ordering || "-updated_at",
    };
    if (params.status) built.status = params.status;
    if (params.q) built.search = params.q;
    if (params.category) built.category = params.category;
    if (params.mine === "1") built.author = "me";
    return built;
  }, [params.page, params.status, params.q, params.category, params.mine, params.ordering]);

  const queryKey = useMemo(
    () => JSON.stringify({ query, refreshToken }),
    [query, refreshToken],
  );

  useEffect(() => {
    let cancelled = false;
    listArticles(query)
      .then((page) => {
        if (!cancelled) setResult({ key: queryKey, data: page });
      })
      .catch((err) => {
        if (cancelled) return;
        setResult({
          key: queryKey,
          error:
            err?.response?.status === 403
              ? "You do not have access to this site's content."
              : "Could not load articles.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [query, queryKey]);

  const loading = result.key !== queryKey;
  const data = result.key === queryKey ? result.data : undefined;
  const error = result.key === queryKey ? result.error : undefined;

  const activeView =
    SAVED_VIEWS.find((view) =>
      Object.entries(view.query).every(([k, v]) => params[k] === v) &&
      Object.keys(view.query).length ===
        Object.keys(params).filter((k) => ["status", "mine"].includes(k)).length,
    )?.key ?? "all";

  const rows = data?.results ?? [];
  const selectedRows = rows.filter((row) => selected.has(row.id));
  const total = data?.count ?? 0;
  const page = Number(params.page || 1);
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggleAll = () =>
    setSelected(
      selected.size === rows.length ? new Set() : new Set(rows.map((r) => r.id)),
    );

  const activeFilters = ["status", "q", "category", "mine"].filter((k) => params[k]);

  return (
    <div className="flex h-full min-w-0">
      {showFilters && (
        <aside className="hidden w-60 shrink-0 border-r border-[var(--sl-line)] bg-[var(--sl-card)] p-4 lg:block">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
              Filters
            </h2>
            {activeFilters.length > 0 && (
              <button
                onClick={() =>
                  setParam({ status: null, q: null, category: null, mine: null })
                }
                className="text-xs text-[var(--sl-accent)] hover:underline"
              >
                Clear
              </button>
            )}
          </div>

          <FilterGroup label="Status">
            {STATUS_OPTIONS.map((option) => (
              <FilterOption
                key={option.value}
                active={params.status === option.value}
                onClick={() =>
                  setParam({
                    status: params.status === option.value ? null : option.value,
                  })
                }
              >
                {option.label}
              </FilterOption>
            ))}
          </FilterGroup>

          {categories.length > 0 && (
            <FilterGroup label="Category">
              {categories.slice(0, 12).map((category) => (
                <FilterOption
                  key={category.id}
                  active={params.category === String(category.id)}
                  onClick={() =>
                    setParam({
                      category:
                        params.category === String(category.id)
                          ? null
                          : String(category.id),
                    })
                  }
                >
                  {category.name}
                </FilterOption>
              ))}
            </FilterGroup>
          )}

          <FilterGroup label="Ownership">
            <FilterOption
              active={params.mine === "1"}
              onClick={() => setParam({ mine: params.mine === "1" ? null : "1" })}
            >
              Written by me
            </FilterOption>
          </FilterGroup>
        </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-[var(--sl-line)] bg-[var(--sl-card)] px-6 py-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="font-display text-2xl font-bold text-[var(--sl-ink)]">
                Content
              </h1>
              <p className="text-sm text-[var(--sl-muted)]">
                {loading ? "Loading…" : `${total} article${total === 1 ? "" : "s"}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setShowFilters((v) => !v)}
                aria-label="Toggle filters"
              >
                <Filter size={17} />
              </Button>
              <Button asChild>
                <Link href="/studio/content/new">
                  <Plus size={16} /> New article
                </Link>
              </Button>
            </div>
          </div>

          {/* Saved views are plain links because the state is in the URL. */}
          <div className="flex flex-wrap items-center gap-1 border-b border-[var(--sl-line)]">
            {SAVED_VIEWS.map((view) => (
              <button
                key={view.key}
                onClick={() =>
                  setParam({
                    status: view.query.status ?? null,
                    mine: view.query.mine ?? null,
                  })
                }
                className={cn(
                  "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                  activeView === view.key
                    ? "border-[var(--sl-soft)] text-[var(--sl-accent)]"
                    : "border-transparent hover:text-[var(--sl-ink)] hover:text-[var(--sl-muted)]",
                )}
              >
                {view.label}
              </button>
            ))}
          </div>

          <div className="relative mt-4 max-w-sm">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--sl-muted)]"
            />
            <input
              type="search"
              defaultValue={params.q || ""}
              placeholder="Search titles and body text…"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  setParam({ q: (event.target as HTMLInputElement).value || null });
                }
              }}
              className="input-field pl-9"
            />
          </div>
        </div>

        {selected.size > 0 && (
          <div className="flex items-center justify-between border-b border-[var(--sl-soft)] bg-[var(--sl-soft)] px-6 py-2.5 text-sm dark:bg-primary-950/40">
            <span className="font-medium text-[var(--sl-accent)]">
              {selected.size} selected
            </span>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => setBulkOpen(true)}>
                Bulk actions
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                <X size={14} /> Clear
              </Button>
            </div>
          </div>
        )}

        <BulkActionDrawer
          open={bulkOpen}
          onOpenChange={setBulkOpen}
          selected={selectedRows}
          onCompleted={() => {
            // Refetch so the table shows the new states, and drop the selection
            // -- keeping it would let a second run hit articles that just moved.
            setSelected(new Set());
            setRefreshToken((n) => n + 1);
          }}
        />

        <div className="min-w-0 flex-1 overflow-auto p-6">
          {error && !loading ? (
            <p className="py-16 text-center text-sm text-red-600">{error}</p>
          ) : loading ? (
            <TableSkeleton />
          ) : rows.length === 0 ? (
            <div className="py-20 text-center">
              <p className="text-[var(--sl-muted)]">
                No articles match these filters.
              </p>
              {activeFilters.length > 0 && (
                <button
                  onClick={() =>
                    setParam({ status: null, q: null, category: null, mine: null })
                  }
                  className="mt-2 text-sm text-[var(--sl-accent)] hover:underline"
                >
                  Clear filters
                </button>
              )}
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead className="border-b border-[var(--sl-line)] bg-[var(--sl-soft)] text-left dark:bg-slate-800/50">
                  <tr>
                    <th className="w-10 px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label="Select all"
                        checked={selected.size === rows.length && rows.length > 0}
                        onChange={toggleAll}
                        className="rounded border-[var(--sl-line)]"
                      />
                    </th>
                    <th className="px-3 py-3 font-semibold text-[var(--sl-ink)]">
                      Title
                    </th>
                    <th className="px-3 py-3 font-semibold text-[var(--sl-ink)]">
                      Status
                    </th>
                    <th className="hidden px-3 py-3 font-semibold text-[var(--sl-ink)] md:table-cell">
                      Author
                    </th>
                    <th className="hidden px-3 py-3 font-semibold text-[var(--sl-ink)] lg:table-cell">
                      Words
                    </th>
                    <th className="hidden px-3 py-3 font-semibold text-[var(--sl-ink)] lg:table-cell">
                      Sites
                    </th>
                    <th className="px-3 py-3 font-semibold text-[var(--sl-ink)]">
                      Updated
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-[var(--sl-line)] last:border-0 hover:bg-[var(--sl-soft)] dark:hover:bg-slate-800/40"
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          aria-label={`Select ${row.title}`}
                          checked={selected.has(row.id)}
                          onChange={() => {
                            const next = new Set(selected);
                            if (next.has(row.id)) next.delete(row.id);
                            else next.add(row.id);
                            setSelected(next);
                          }}
                          className="rounded border-[var(--sl-line)]"
                        />
                      </td>
                      <td className="px-3 py-3">
                        <Link
                          href={`/studio/content/${encodeURIComponent(row.slug)}`}
                          className="font-medium text-[var(--sl-ink)] hover:text-[var(--sl-accent)]"
                        >
                          {row.title || "Untitled"}
                        </Link>
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="hidden px-3 py-3 text-[var(--sl-muted)] md:table-cell">
                        {row.author?.name || "—"}
                      </td>
                      <td className="hidden px-3 py-3 text-[var(--sl-muted)] lg:table-cell">
                        {row.word_count.toLocaleString()}
                      </td>
                      <td className="hidden px-3 py-3 lg:table-cell">
                        <Badge tone={row.placement_count ? "blue" : "slate"}>
                          {row.placement_count ?? 0}
                        </Badge>
                      </td>
                      <td className="px-3 py-3 text-[var(--sl-muted)]">
                        {new Date(row.updated_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {pageCount > 1 && (
            <nav className="mt-5 flex items-center justify-center gap-2" aria-label="Pagination">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => setParam({ page: String(page - 1) })}
              >
                Previous
              </Button>
              <span className="text-sm text-[var(--sl-muted)]">
                Page {page} of {pageCount}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= pageCount}
                onClick={() => setParam({ page: String(page + 1) })}
              >
                Next
              </Button>
            </nav>
          )}
        </div>
      </div>
    </div>
  );
}

function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
        {label}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function FilterOption({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "block w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors",
        active
          ? "bg-[var(--sl-soft)] font-medium text-[var(--sl-accent)] dark:bg-primary-950/50"
          : "text-[var(--sl-ink)] hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]",
      )}
    >
      {children}
    </button>
  );
}

function TableSkeleton() {
  return (
    <div className="card divide-y divide-[var(--sl-line)]">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="flex items-center gap-4 px-4 py-4">
          <div className="h-4 w-4 animate-pulse rounded bg-[var(--sl-soft)]" />
          <div className="h-4 flex-1 animate-pulse rounded bg-[var(--sl-soft)]" />
          <div className="h-4 w-20 animate-pulse rounded bg-[var(--sl-soft)]" />
        </div>
      ))}
    </div>
  );
}
