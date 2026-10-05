"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listArticles, type StudioArticleRow } from "@/lib/studio-api";
import { useAuth } from "@/lib/auth";
import { Eye, Calendar, Edit2 } from "lucide-react";

export default function MyArticlesPage() {
  const { user } = useAuth();
  const [articles, setArticles] = useState<StudioArticleRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    // The removed `/articles/my-articles/` action is now `?author=<id>` on the
    // one article list -- the same queryset, filtered, instead of a second
    // endpoint that could drift from it.
    listArticles({ author: user.id, page_size: 50, ordering: "-updated_at" })
      .then((page) => setArticles(page.results))
      .catch(() => setArticles([]))
      .finally(() => setLoading(false));
  }, [user]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--sl-soft)]" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-[var(--sl-ink)] mb-8">
        My Articles
      </h1>

      {articles.length === 0 ? (
        <div className="text-center py-12 text-[var(--sl-muted)]">
          You haven&apos;t written any articles yet.
        </div>
      ) : (
        <div className="space-y-4">
          {articles.map((article) => (
            <div key={article.id} className="card p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <Link
                    href={`/articles/${article.slug}`}
                    className="text-lg font-semibold text-[var(--sl-ink)] hover:text-[var(--sl-accent)] transition"
                  >
                    {article.title}
                  </Link>
                  {article.excerpt && (
                    <p className="text-sm text-[var(--sl-muted)] mt-1 line-clamp-2">
                      {article.excerpt}
                    </p>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-xs text-[var(--sl-muted)]">
                    <span
                      className={`px-2 py-0.5 rounded-full font-medium ${
                        article.status === "published"
                          ? "bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400"
                          : "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400"
                      }`}
                    >
                      {article.status}
                    </span>
                    <span className="flex items-center gap-1">
                      <Eye className="w-3 h-3" />
                      {article.views_count}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {new Date(article.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <Link
                  href={`/studio/content/${encodeURIComponent(article.slug)}`}
                  className="p-2 hover:bg-[var(--sl-soft)] rounded-lg transition"
                >
                  <Edit2 className="w-4 h-4 text-[var(--sl-muted)]" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
