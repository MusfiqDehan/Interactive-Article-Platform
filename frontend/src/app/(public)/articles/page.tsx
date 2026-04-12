"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { Search, BookOpen, ChevronLeft, ChevronRight } from "lucide-react";
import api from "@/lib/api";
import { ArticleListItem, Category, PaginatedResponse } from "@/lib/types";

export default function ArticlesPage() {
  const [articles, setArticles] = useState<ArticleListItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchArticles = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      params.set("page_size", "9");
      if (search) params.set("search", search);
      if (selectedCategory) params.set("category", selectedCategory);

      const response = await api.get<PaginatedResponse<ArticleListItem>>(
        `/articles/?${params.toString()}`
      );
      setArticles(response.data.results);
      setTotalPages(Math.ceil(response.data.count / 9));
    } catch {
      setArticles([]);
    } finally {
      setIsLoading(false);
    }
  }, [page, search, selectedCategory]);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await api.get("/categories/");
        setCategories(response.data.results || response.data || []);
      } catch {
        // ignore
      }
    };
    fetchCategories();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Page Header */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-4">All Articles</h1>
        <p className="text-lg text-slate-500 dark:text-slate-400">
          Explore our collection of interactive articles
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-10">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
          <input
            type="text"
            placeholder="Search articles..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="input-field pl-10"
          />
        </div>
        <select
          value={selectedCategory}
          onChange={(e) => {
            setSelectedCategory(e.target.value);
            setPage(1);
          }}
          className="input-field md:w-64"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>
              {cat.name}
            </option>
          ))}
        </select>
      </div>

      {/* Articles Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-48 bg-slate-200 dark:bg-slate-700 rounded-t-xl" />
              <div className="p-6 space-y-3">
                <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/4" />
                <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded w-3/4" />
                <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : articles.length === 0 ? (
        <div className="text-center py-20">
          <BookOpen className="w-16 h-16 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-slate-600 dark:text-slate-400 mb-2">
            No articles found
          </h3>
          <p className="text-slate-500 dark:text-slate-500">
            Try adjusting your search or filter criteria
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {articles.map((article) => (
              <Link
                key={article.id}
                href={`/articles/${article.slug}`}
                className="card overflow-hidden group hover:shadow-xl transition-all hover:-translate-y-1"
              >
                {article.featured_image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={article.featured_image}
                    alt={article.title}
                    className="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                ) : (
                  <div className="w-full h-48 bg-gradient-to-br from-primary-100 to-accent-100 dark:from-primary-900/30 dark:to-accent-900/30 flex items-center justify-center">
                    <BookOpen className="w-12 h-12 text-primary-400" />
                  </div>
                )}
                <div className="p-6">
                  {article.category && (
                    <span className="inline-block px-3 py-1 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 text-xs font-medium mb-3">
                      {article.category.name}
                    </span>
                  )}
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2 line-clamp-2 group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">
                    {article.title}
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2 mb-4">
                    {article.excerpt}
                  </p>
                  <div className="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
                    <span>{article.author.first_name || article.author.username}</span>
                    <span>{article.reading_time} min read</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-12">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary px-3 py-2"
              >
                <ChevronLeft size={18} />
              </button>
              <span className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-secondary px-3 py-2"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
