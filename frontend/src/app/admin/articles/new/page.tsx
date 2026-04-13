"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
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

export default function NewArticlePage() {
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [featuredImage, setFeaturedImage] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [subcategoryId, setSubcategoryId] = useState<number | "">("");
  const [status, setStatus] = useState<"draft" | "published">("draft");
  const [isFeatured, setIsFeatured] = useState(false);
  const [editorData, setEditorData] = useState<OutputData>({ blocks: [] });

  const [categories, setCategories] = useState<Category[]>([]);
  const [subcategories, setSubcategories] = useState<SubCategory[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const res = await api.get("/categories/");
        setCategories(res.data.results || res.data);
      } catch {
        // silent
      }
    };
    fetchCategories();
  }, []);

  useEffect(() => {
    if (categoryId) {
      const selected = categories.find((c) => c.id === categoryId);
      setSubcategories(selected?.subcategories || []);
      setSubcategoryId("");
    } else {
      setSubcategories([]);
      setSubcategoryId("");
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
        featured_image: featuredImage || null,
        category: categoryId,
        subcategory: subcategoryId || null,
        status,
        is_featured: isFeatured,
        content: editorData,
      };

      await api.post("/articles/", payload);
      router.push("/admin/articles");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: Record<string, string[]> } };
      if (axiosErr.response?.data) {
        const messages = Object.entries(axiosErr.response.data)
          .map(([key, val]) => `${key}: ${Array.isArray(val) ? val.join(", ") : val}`)
          .join("; ");
        setError(messages);
      } else {
        setError("Failed to create article");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("image", file);
    try {
      const res = await api.post("/media/upload/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (res.data?.file?.url) {
        setFeaturedImage(res.data.file.url);
      }
    } catch {
      setError("Failed to upload image");
    }
  };

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
            New Article
          </h1>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Title */}
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

        {/* Excerpt */}
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

        {/* Category & Subcategory */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Category *
            </label>
            <select
              value={categoryId}
              onChange={(e) =>
                setCategoryId(e.target.value ? Number(e.target.value) : "")
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

        {/* Featured Image */}
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
                src={featuredImage}
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

        {/* Status & Featured */}
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

        {/* Editor */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Content
          </label>
          <Editor
            data={editorData}
            onChange={handleEditorChange}
            holder="new-article-editor"
          />
        </div>

        {/* Interactive Content Help */}
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

        {/* Actions */}
        <div className="flex items-center justify-end gap-4 pt-4 border-t border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => router.push("/admin/articles")}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2">
            <Save className="w-4 h-4" />
            {saving ? "Saving..." : "Save Article"}
          </button>
        </div>
      </form>
    </div>
  );
}
