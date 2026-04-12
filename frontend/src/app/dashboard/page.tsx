"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import api from "@/lib/api";
import { FileText, Eye, BookOpen } from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState({ total: 0, published: 0, views: 0 });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await api.get("/articles/stats/");
        setStats({
          total: res.data.total_articles || 0,
          published: res.data.published_articles || 0,
          views: res.data.total_views || 0,
        });
      } catch {
        // silent
      }
    };
    fetchStats();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
        Welcome back, {user?.first_name || user?.username}!
      </h1>
      <p className="text-slate-500 dark:text-slate-400 mb-8">
        Here&apos;s an overview of your activity.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
              <FileText className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {stats.total}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
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
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {stats.published}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
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
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {stats.views}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Total Views
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
