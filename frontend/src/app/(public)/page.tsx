"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, Sparkles, Layers, Play, MousePointerClick } from "lucide-react";
import api from "@/lib/api";
import { ArticleListItem, Category } from "@/lib/types";

export default function LandingPage() {
  const [featuredArticles, setFeaturedArticles] = useState<ArticleListItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [recentArticles, setRecentArticles] = useState<ArticleListItem[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [featuredRes, categoriesRes, recentRes] = await Promise.all([
          api.get("/articles/featured/").catch(() => ({ data: [] })),
          api.get("/categories/").catch(() => ({ data: { results: [] } })),
          api.get("/articles/?page_size=6").catch(() => ({ data: { results: [] } })),
        ]);
        setFeaturedArticles(featuredRes.data);
        setCategories(categoriesRes.data.results || categoriesRes.data || []);
        setRecentArticles(recentRes.data.results || []);
      } catch {
        // API may not be available yet
      }
    };
    fetchData();
  }, []);

  const features = [
    {
      icon: <Sparkles className="w-6 h-6" />,
      title: "Rich Text Formatting",
      description: "Bold, italic, underline, and more — format your articles with full control.",
    },
    {
      icon: <Play className="w-6 h-6" />,
      title: "Multimedia Support",
      description: "Embed images, audio, local videos, and YouTube content seamlessly.",
    },
    {
      icon: <MousePointerClick className="w-6 h-6" />,
      title: "Interactive Modals",
      description: "Create clickable text and image hotspots that reveal detailed explanations.",
    },
    {
      icon: <Layers className="w-6 h-6" />,
      title: "Content Hierarchy",
      description: "Organize articles with categories and subcategories for easy navigation.",
    },
  ];

  return (
    <div>
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-600 via-primary-700 to-accent-700" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PGNpcmNsZSBjeD0iMzAiIGN5PSIzMCIgcj0iMiIvPjwvZz48L2c+PC9zdmc+')] opacity-40" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-32">
          <div className="text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 text-white/90 text-sm mb-8">
              <Sparkles size={16} />
              <span>Dynamic & Interactive Content Platform</span>
            </div>
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-white mb-6 leading-tight">
              Articles That Come
              <br />
              <span className="bg-gradient-to-r from-yellow-300 to-orange-300 bg-clip-text text-transparent">
                Alive
              </span>
            </h1>
            <p className="text-lg md:text-xl text-white/80 max-w-2xl mx-auto mb-10">
              Create and explore interactive articles with rich multimedia, clickable elements,
              and engaging content that goes beyond traditional reading.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/articles"
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-white text-primary-700 font-semibold shadow-lg hover:shadow-xl hover:bg-slate-50 transition-all text-base"
              >
                <BookOpen size={20} />
                Explore Articles
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl border-2 border-white/30 text-white font-semibold hover:bg-white/10 transition-all text-base"
              >
                Start Writing
                <ArrowRight size={20} />
              </Link>
            </div>
          </div>
        </div>
        {/* Wave SVG */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M0 120L60 105C120 90 240 60 360 52.5C480 45 600 60 720 67.5C840 75 960 75 1080 67.5C1200 60 1320 45 1380 37.5L1440 30V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0Z"
              className="fill-white dark:fill-slate-950"
            />
          </svg>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-white dark:bg-slate-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-4">
              Powerful Features
            </h2>
            <p className="text-lg text-slate-500 dark:text-slate-400 max-w-2xl mx-auto">
              Everything you need to create compelling, interactive content
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div
                key={index}
                className="card p-6 hover:shadow-lg transition-all hover:-translate-y-1 group"
              >
                <div className="w-12 h-12 rounded-xl bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  {feature.icon}
                </div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Articles */}
      {featuredArticles.length > 0 && (
        <section className="py-20 bg-slate-50 dark:bg-slate-900">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between mb-12">
              <div>
                <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
                  Featured Articles
                </h2>
                <p className="text-slate-500 dark:text-slate-400">
                  Hand-picked content worth exploring
                </p>
              </div>
              <Link
                href="/articles"
                className="hidden sm:inline-flex items-center gap-1 text-primary-600 dark:text-primary-400 font-medium hover:gap-2 transition-all"
              >
                View all <ArrowRight size={16} />
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {featuredArticles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Categories Section */}
      {categories.length > 0 && (
        <section className="py-20 bg-white dark:bg-slate-950">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
                Browse by Category
              </h2>
              <p className="text-slate-500 dark:text-slate-400">
                Find articles organized by topic
              </p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {categories.map((category) => (
                <Link
                  key={category.id}
                  href={`/categories/${category.slug}`}
                  className="card p-6 text-center hover:shadow-lg transition-all hover:-translate-y-1 group"
                >
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-100 to-accent-100 dark:from-primary-900/30 dark:to-accent-900/30 flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform">
                    <Layers className="w-6 h-6 text-primary-600 dark:text-primary-400" />
                  </div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-1">
                    {category.name}
                  </h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {category.article_count} article{category.article_count !== 1 ? "s" : ""}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Recent Articles */}
      {recentArticles.length > 0 && (
        <section className="py-20 bg-slate-50 dark:bg-slate-900">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between mb-12">
              <div>
                <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
                  Latest Articles
                </h2>
                <p className="text-slate-500 dark:text-slate-400">
                  Fresh content from our authors
                </p>
              </div>
              <Link
                href="/articles"
                className="hidden sm:inline-flex items-center gap-1 text-primary-600 dark:text-primary-400 font-medium hover:gap-2 transition-all"
              >
                View all <ArrowRight size={16} />
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {recentArticles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* CTA Section */}
      <section className="py-20 bg-white dark:bg-slate-950">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            Ready to Create Interactive Content?
          </h2>
          <p className="text-lg text-slate-500 dark:text-slate-400 mb-8 max-w-2xl mx-auto">
            Join our platform and start building articles with rich multimedia,
            interactive elements, and engaging content that captivates your audience.
          </p>
          <Link
            href="/register"
            className="btn-primary px-8 py-3.5 text-base"
          >
            Get Started Free
            <ArrowRight size={20} className="ml-2" />
          </Link>
        </div>
      </section>
    </div>
  );
}

function ArticleCard({ article }: { article: ArticleListItem }) {
  return (
    <Link href={`/articles/${article.slug}`} className="card overflow-hidden group hover:shadow-xl transition-all hover:-translate-y-1">
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
  );
}
