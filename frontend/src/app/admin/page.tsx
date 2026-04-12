"use client";

import { useEffect, useState } from "react";
import { FileText, Eye, Layers, Users } from "lucide-react";
import api from "@/lib/api";
import { StatsResponse } from "@/lib/types";

export default function AdminDashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await api.get("/articles/stats/");
        setStats(response.data);
      } catch {
        // ignore
      }
    };
    fetchStats();
  }, []);

  const statCards = [
    { label: "Total Articles", value: stats?.total_articles ?? 0, icon: FileText, color: "bg-blue-500" },
    { label: "Published", value: stats?.published_articles ?? 0, icon: FileText, color: "bg-green-500" },
    { label: "Total Views", value: stats?.total_views ?? 0, icon: Eye, color: "bg-purple-500" },
    { label: "Categories", value: stats?.total_categories ?? 0, icon: Layers, color: "bg-orange-500" },
    ...(stats?.total_users != null
      ? [{ label: "Total Users", value: stats.total_users, icon: Users, color: "bg-pink-500" }]
      : []),
  ];

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Dashboard</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Overview of your platform</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
        {statCards.map((stat, index) => (
          <div key={index} className="card p-6">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl ${stat.color} flex items-center justify-center`}>
                <stat.icon size={22} className="text-white" />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">{stat.value}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">{stat.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
