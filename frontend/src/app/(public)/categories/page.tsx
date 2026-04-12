"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Layers } from "lucide-react";
import api from "@/lib/api";
import { Category } from "@/lib/types";

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await api.get("/categories/");
        setCategories(response.data.results || response.data || []);
      } catch {
        setCategories([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchCategories();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-4">Categories</h1>
        <p className="text-lg text-slate-500 dark:text-slate-400">
          Browse articles by topic
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card p-6 animate-pulse">
              <div className="h-12 w-12 rounded-xl bg-slate-200 dark:bg-slate-700 mb-4" />
              <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded w-1/3 mb-2" />
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-2/3" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {categories.map((category) => (
            <Link
              key={category.id}
              href={`/categories/${category.slug}`}
              className="card p-6 hover:shadow-lg transition-all hover:-translate-y-1 group"
            >
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-100 to-accent-100 dark:from-primary-900/30 dark:to-accent-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Layers className="w-6 h-6 text-primary-600 dark:text-primary-400" />
              </div>
              <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">
                {category.name}
              </h3>
              {category.description && (
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-3 line-clamp-2">
                  {category.description}
                </p>
              )}
              <p className="text-sm text-primary-600 dark:text-primary-400 font-medium">
                {category.article_count} article{category.article_count !== 1 ? "s" : ""}
              </p>
              {category.subcategories && category.subcategories.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {category.subcategories.map((sub) => (
                    <span
                      key={sub.id}
                      className="px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-700 text-xs text-slate-600 dark:text-slate-400"
                    >
                      {sub.name}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
