"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import api from "@/lib/api";
import { normalizeMediaUrl } from "@/lib/media";
import type { Category, SubCategory } from "@/lib/types";
import type { OutputData } from "@editorjs/editorjs";
import { ArrowLeft, Save } from "lucide-react";
import dynamic_import from "next/dynamic";

const Editor = dynamic_import(() => import("@/components/editor/Editor"), {
  ssr: false,
  loading: () => (
    <div className="min-h-[400px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
    </div>
  ),
});

function normalizeEditorData(data: OutputData): OutputData {
  const blocks = Array.isArray(data?.blocks)
    ? data.blocks.filter(
        (block): block is NonNullable<OutputData["blocks"]>[number] =>
          Boolean(
            block &&
              typeof block === "object" &&
              typeof block.type === "string" &&
              block.type.trim().length > 0 &&
              block.data &&
              typeof block.data === "object"
          )
      )
    : [];

  return {
    ...data,
    blocks,
  };
}

function getApiErrorMessage(err: unknown, fallback: string): string {
  const axiosErr = err as {
    message?: string;
    response?: { status?: number; data?: unknown };
  };

  if (axiosErr.response?.data) {
    if (typeof axiosErr.response.data === "string") {
      return axiosErr.response.data;
    }

    if (typeof axiosErr.response.data === "object") {
      const entries = Object.entries(
        axiosErr.response.data as Record<string, unknown>
      );
      if (entries.length > 0) {
        return entries
          .map(([key, val]) => {
            if (Array.isArray(val)) {
              return `${key}: ${val.join(", ")}`;
            }
            return `${key}: ${String(val)}`;
          })
          .join("; ");
      }
    }
  }

  if (axiosErr.message) {
    return `${fallback}: ${axiosErr.message}`;
  }

  if (axiosErr.response?.status) {
    return `${fallback} (HTTP ${axiosErr.response.status})`;
  }

  return fallback;
}

export default function EditArticlePage() {
  const router = useRouter();
  const params = useParams();
  const articleSlug = params.slug as string;

  const [title, setTitle] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [featuredImage, setFeaturedImage] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [subcategoryId, setSubcategoryId] = useState<number | "">("");
  const [status, setStatus] = useState<"draft" | "published">("draft");
  const [isFeatured, setIsFeatured] = useState(false);
  const [editorData, setEditorData] = useState<OutputData | null>(null);

  const [categories, setCategories] = useState<Category[]>([]);
  const [subcategories, setSubcategories] = useState<SubCategory[]>([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [catRes, articleRes] = await Promise.all([
          api.get("/categories/"),
          api.get(`/articles/${articleSlug}/`),
        ]);

        const cats = catRes.data.results || catRes.data;
        setCategories(cats);

        const article = articleRes.data;
        setTitle(article.title);
        setExcerpt(article.excerpt || "");
        setFeaturedImage(normalizeMediaUrl(article.featured_image || ""));
        setCategoryId(article.category?.id || article.category || "");
        setSubcategoryId(article.subcategory?.id || article.subcategory || "");
        setStatus(article.status);
        setIsFeatured(article.is_featured);
        setEditorData(article.content || { blocks: [] });

        // Set subcategories from the selected category
        if (article.category) {
          const catId =
            typeof article.category === "object"
              ? article.category.id
              : article.category;
          const selectedCat = cats.find(
            (c: Category) => c.id === catId
          );
          if (selectedCat) {
            setSubcategories(selectedCat.subcategories || []);
          }
        }
      } catch {
        setError("Failed to load article");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [articleSlug]);

  useEffect(() => {
    if (categoryId && categories.length > 0) {
      const selected = categories.find((c) => c.id === categoryId);
      setSubcategories(selected?.subcategories || []);
    }
  }, [categoryId, categories]);

  const handleEditorChange = useCallback((data: OutputData) => {
    setEditorData(data);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    if (!categoryId) {
      setError("Category is required");
      return;
    }

    setSaving(true);
    setError("");

    try {
      const payload: Record<string, unknown> = {
        title,
        excerpt,
        featured_image: featuredImage.trim(),
        category: categoryId,
        subcategory: subcategoryId || null,
        status,
        is_featured: isFeatured,
        content: normalizeEditorData(editorData || { blocks: [] }),
      };

      await api.put(`/articles/${articleSlug}/`, payload);
      router.push("/admin/articles");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to update article"));
    } finally {
      setSaving(false);
    }
  };

  const handleImageUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("image", file);
    try {
      const res = await api.post("/media/upload/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (res.data?.file?.url) {
        setFeaturedImage(normalizeMediaUrl(res.data.file.url));
      }
    } catch {
      setError("Failed to upload image");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push("/admin/articles")}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Edit Article
          </h1>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Title *
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter article title"
            className="input-field text-lg"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Excerpt
          </label>
          <textarea
            value={excerpt}
            onChange={(e) => setExcerpt(e.target.value)}
            placeholder="Brief summary of the article"
            rows={3}
            className="input-field"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Category *
            </label>
            <select
              value={categoryId}
              onChange={(e) =>
                setCategoryId(
                  e.target.value ? Number(e.target.value) : ""
                )
              }
              className="input-field"
              required
            >
              <option value="">Select category</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Subcategory
            </label>
            <select
              value={subcategoryId}
              onChange={(e) =>
                setSubcategoryId(
                  e.target.value ? Number(e.target.value) : ""
                )
              }
              className="input-field"
              disabled={!categoryId}
            >
              <option value="">Select subcategory</option>
              {subcategories.map((sub) => (
                <option key={sub.id} value={sub.id}>
                  {sub.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Featured Image
          </label>
          <div className="flex items-center gap-4">
            <input
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="input-field flex-1"
            />
            {featuredImage && (
              <img
                src={normalizeMediaUrl(featuredImage)}
                alt="Featured"
                className="w-20 h-20 object-cover rounded-lg"
              />
            )}
          </div>
          <input
            type="text"
            value={featuredImage}
            onChange={(e) => setFeaturedImage(e.target.value)}
            placeholder="Or paste image URL"
            className="input-field mt-2"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Status
            </label>
            <select
              value={status}
              onChange={(e) =>
                setStatus(e.target.value as "draft" | "published")
              }
              className="input-field"
            >
              <option value="draft">Draft</option>
              <option value="published">Published</option>
            </select>
          </div>
          <div className="flex items-center gap-3 pt-8">
            <input
              type="checkbox"
              id="is_featured"
              checked={isFeatured}
              onChange={(e) => setIsFeatured(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            />
            <label
              htmlFor="is_featured"
              className="text-sm font-medium text-slate-700 dark:text-slate-300"
            >
              Featured Article
            </label>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Content
          </label>
          {editorData && (
            <Editor
              data={editorData}
              onChange={handleEditorChange}
              holder="edit-article-editor"
            />
          )}
        </div>

        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
          <h3 className="font-medium text-blue-800 dark:text-blue-300 mb-2">
            Interactive Content Tips
          </h3>
          <ul className="text-sm text-blue-600 dark:text-blue-400 space-y-1 list-disc list-inside">
            <li>
              Use the <strong>Interactive Text</strong> block to type a paragraph, then{" "}
              <strong>select any words</strong> to attach a text explanation, image, audio, video, or YouTube embed — a blue highlight and 🔍 icon will appear on those words.
            </li>
            <li>
              Use the <strong>Interactive Image</strong> block to upload an image and{" "}
              <strong>click directly on it</strong> to place clickable hotspot regions.
            </li>
            <li>
              Use <strong>Interactive Audio</strong>, <strong>Interactive Video</strong>, or{" "}
              <strong>Interactive YouTube</strong> blocks to attach timed chapters that open info modals.
            </li>
          </ul>
        </div>

        <div className="flex items-center justify-end gap-4 pt-4 border-t border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => router.push("/admin/articles")}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="btn-primary flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {saving ? "Saving..." : "Update Article"}
          </button>
        </div>
      </form>
    </div>
  );
}
