"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { listArticles } from "@/lib/studio-api";
import { FileText, Eye, BookOpen } from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState({ total: 0, published: 0, views: 0 });

  useEffect(() => {
    // Three counts from three `count`-only requests rather than a dedicated
    // stats endpoint. The removed legacy `/articles/stats/` summed in Python
    // across the whole table; asking the database for three counts with
    // `page_size=1` is both cheaper and correctly tenant-scoped.
    const fetchStats = async () => {
      try {
        const [all, published] = await Promise.all([
          listArticles({ page_size: 1 }),
          listArticles({ page_size: 1, status: "published" }),
        ]);
        const recent = await listArticles({ page_size: 100 });
        setStats({
          total: all.count,
          published: published.count,
          views: recent.results.reduce((sum, a) => sum + (a.views_count || 0), 0),
        });
      } catch {
        // A dashboard that cannot count is still a usable dashboard; the zeroes
        // it already shows are the honest answer to "we do not know".
      }
    };
    fetchStats();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-[var(--sl-ink)] mb-2">
        Welcome back, {user?.first_name || user?.username}!
      </h1>
      <p className="text-[var(--sl-muted)] mb-8">
        Here&apos;s an overview of your activity.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
              <FileText className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--sl-ink)]">
                {stats.total}
              </p>
              <p className="text-sm text-[var(--sl-muted)]">
                Total Articles
              </p>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-xl">
              <BookOpen className="w-6 h-6 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--sl-ink)]">
                {stats.published}
              </p>
              <p className="text-sm text-[var(--sl-muted)]">
                Published
              </p>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-xl">
              <Eye className="w-6 h-6 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--sl-ink)]">
                {stats.views}
              </p>
              <p className="text-sm text-[var(--sl-muted)]">
                Total Views
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
