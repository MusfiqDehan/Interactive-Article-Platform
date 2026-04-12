"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { ArticleListItem } from "@/lib/types";
import { Eye, Calendar, Edit2 } from "lucide-react";

export default function MyArticlesPage() {
  const [articles, setArticles] = useState<ArticleListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchArticles = async () => {
      try {
        const res = await api.get("/articles/my-articles/");
        setArticles(res.data.results || res.data);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    };
    fetchArticles();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-8">
        My Articles
      </h1>

      {articles.length === 0 ? (
        <div className="text-center py-12 text-slate-500 dark:text-slate-400">
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
                    className="text-lg font-semibold text-slate-900 dark:text-white hover:text-primary-600 transition"
                  >
                    {article.title}
                  </Link>
                  {article.excerpt && (
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                      {article.excerpt}
                    </p>
                  )}
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
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
                  href={`/admin/articles/${article.slug}/edit`}
                  className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition"
                >
                  <Edit2 className="w-4 h-4 text-slate-500" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
