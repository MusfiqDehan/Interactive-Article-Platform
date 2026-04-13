"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Clock, Eye, Calendar, User } from "lucide-react";
import api from "@/lib/api";
import { normalizeMediaUrl } from "@/lib/media";
import { Article } from "@/lib/types";
import BlockRenderer from "@/components/article/BlockRenderer";

export default function ArticleDetailPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [article, setArticle] = useState<Article | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        const response = await api.get(`/articles/${slug}/`);
        setArticle(response.data);
        // Increment view count
        api.post(`/articles/${slug}/view/`).catch(() => {});
      } catch {
        setArticle(null);
      } finally {
        setIsLoading(false);
      }
    };
    if (slug) fetchArticle();
  }, [slug]);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="animate-pulse space-y-6">
          <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-24" />
          <div className="h-10 bg-slate-200 dark:bg-slate-700 rounded w-3/4" />
          <div className="flex gap-4">
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-32" />
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-24" />
          </div>
          <div className="h-64 bg-slate-200 dark:bg-slate-700 rounded-xl" />
          <div className="space-y-3">
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded" />
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-5/6" />
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-4/6" />
          </div>
        </div>
      </div>
    );
  }

  if (!article) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
          Article Not Found
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mb-6">
          The article you&apos;re looking for doesn&apos;t exist or has been removed.
        </p>
        <Link href="/articles" className="btn-primary">
          <ArrowLeft size={18} className="mr-2" />
          Back to Articles
        </Link>
      </div>
    );
  }

  return (
    <article className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Back link */}
      <Link
        href="/articles"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-primary-600 dark:text-slate-400 dark:hover:text-primary-400 mb-8 transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Articles
      </Link>

      {/* Article header */}
      <header className="mb-10">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          {article.category && (
            <Link
              href={`/categories/${article.category.slug}`}
              className="px-3 py-1 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 text-xs font-medium hover:bg-primary-200 dark:hover:bg-primary-900/50 transition-colors"
            >
              {article.category.name}
            </Link>
          )}
          {article.subcategory && (
            <span className="px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-medium">
              {article.subcategory.name}
            </span>
          )}
        </div>

        <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-slate-900 dark:text-white mb-6 leading-tight">
          {article.title}
        </h1>

        {article.excerpt && (
          <p className="text-lg text-slate-500 dark:text-slate-400 mb-6">
            {article.excerpt}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-6 text-sm text-slate-500 dark:text-slate-400 pb-8 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
              <User size={16} className="text-primary-600 dark:text-primary-400" />
            </div>
            <span>{article.author.first_name || article.author.username}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar size={16} />
            <span>
              {article.published_at
                ? new Date(article.published_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })
                : "Draft"}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock size={16} />
            <span>{article.reading_time} min read</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Eye size={16} />
            <span>{article.views_count} views</span>
          </div>
        </div>
      </header>

      {/* Featured image */}
      {article.featured_image && (
        <div className="mb-10 rounded-2xl overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={normalizeMediaUrl(article.featured_image)}
            alt={article.title}
            className="w-full h-auto object-cover"
          />
        </div>
      )}

      {/* Article content */}
      <div className="mb-16">
        <BlockRenderer blocks={article.content?.blocks || []} />
      </div>
    </article>
  );
}
