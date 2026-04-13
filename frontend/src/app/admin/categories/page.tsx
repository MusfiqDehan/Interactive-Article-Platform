"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import type { Category } from "@/lib/types";
import { Plus, Edit2, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import Modal from "@/components/ui/Modal";

export default function AdminCategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Category modal
  const [showCatModal, setShowCatModal] = useState(false);
  const [editingCat, setEditingCat] = useState<Category | null>(null);
  const [catName, setCatName] = useState("");
  const [catDescription, setCatDescription] = useState("");
  const [catSaving, setCatSaving] = useState(false);

  // Subcategory modal
  const [showSubModal, setShowSubModal] = useState(false);
  const [subParentId, setSubParentId] = useState<number | null>(null);
  const [editingSubId, setEditingSubId] = useState<number | null>(null);
  const [subName, setSubName] = useState("");
  const [subSaving, setSubSaving] = useState(false);

  const [error, setError] = useState("");

  const fetchCategories = async () => {
    try {
      const res = await api.get("/categories/");
      setCategories(res.data.results || res.data);
    } catch {
      setError("Failed to load categories");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
  }, []);

  // Category CRUD
  const openNewCat = () => {
    setEditingCat(null);
    setCatName("");
    setCatDescription("");
    setShowCatModal(true);
  };

  const openEditCat = (cat: Category) => {
    setEditingCat(cat);
    setCatName(cat.name);
    setCatDescription(cat.description || "");
    setShowCatModal(true);
  };

  const saveCat = async () => {
    if (!catName.trim()) return;
    setCatSaving(true);
    setError("");
    try {
      if (editingCat) {
        await api.put(`/categories/${editingCat.slug}/`, {
          name: catName,
          description: catDescription,
        });
      } else {
        await api.post("/categories/", {
          name: catName,
          description: catDescription,
        });
      }
      setShowCatModal(false);
      fetchCategories();
    } catch {
      setError("Failed to save category");
    } finally {
      setCatSaving(false);
    }
  };

  const deleteCat = async (slug: string) => {
    if (!confirm("Delete this category and all its subcategories?")) return;
    try {
      await api.delete(`/categories/${slug}/`);
      fetchCategories();
    } catch {
      setError("Failed to delete category");
    }
  };

  // Subcategory CRUD
  const openNewSub = (parentId: number) => {
    setSubParentId(parentId);
    setEditingSubId(null);
    setSubName("");
    setShowSubModal(true);
  };

  const openEditSub = (parentId: number, subId: number, name: string) => {
    setSubParentId(parentId);
    setEditingSubId(subId);
    setSubName(name);
    setShowSubModal(true);
  };

  const saveSub = async () => {
    if (!subName.trim() || !subParentId) return;
    setSubSaving(true);
    setError("");
    try {
      if (editingSubId) {
        await api.put(`/categories/subcategories/${editingSubId}/`, {
          name: subName,
          category: subParentId,
        });
      } else {
        await api.post("/categories/subcategories/", {
          name: subName,
          category: subParentId,
        });
      }
      setShowSubModal(false);
      fetchCategories();
    } catch {
      setError("Failed to save subcategory");
    } finally {
      setSubSaving(false);
    }
  };

  const deleteSub = async (id: number) => {
    if (!confirm("Delete this subcategory?")) return;
    try {
      await api.delete(`/categories/subcategories/${id}/`);
      fetchCategories();
    } catch {
      setError("Failed to delete subcategory");
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
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Categories
        </h1>
        <button onClick={openNewCat} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          New Category
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {categories.length === 0 ? (
          <div className="text-center py-12 text-slate-500 dark:text-slate-400">
            No categories yet. Create your first one!
          </div>
        ) : (
          categories.map((cat) => (
            <div
              key={cat.id}
              className="card overflow-hidden"
            >
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() =>
                      setExpandedId(expandedId === cat.id ? null : cat.id)
                    }
                    className="p-1 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
                  >
                    {expandedId === cat.id ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </button>
                  <div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">
                      {cat.name}
                    </h3>
                    {cat.description && (
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {cat.description}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-2 py-1 rounded-full">
                    {cat.subcategories?.length || 0} subcategories
                  </span>
                  <span className="text-xs bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 px-2 py-1 rounded-full">
                    {cat.article_count || 0} articles
                  </span>
                  <button
                    onClick={() => openEditCat(cat)}
                    className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition"
                  >
                    <Edit2 className="w-4 h-4 text-slate-600 dark:text-slate-400" />
                  </button>
                  <button
                    onClick={() => deleteCat(cat.slug)}
                    className="p-2 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>

              {expandedId === cat.id && (
                <div className="border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-slate-600 dark:text-slate-400">
                      Subcategories
                    </h4>
                    <button
                      onClick={() => openNewSub(cat.id)}
                      className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
                    >
                      <Plus className="w-3 h-3" />
                      Add
                    </button>
                  </div>
                  {cat.subcategories && cat.subcategories.length > 0 ? (
                    <div className="space-y-2">
                      {cat.subcategories.map((sub) => (
                        <div
                          key={sub.id}
                          className="flex items-center justify-between bg-white dark:bg-slate-800 rounded-lg p-3"
                        >
                          <span className="text-sm text-slate-700 dark:text-slate-300">
                            {sub.name}
                          </span>
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() =>
                                openEditSub(cat.id, sub.id, sub.name)
                              }
                              className="p-1 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
                            >
                              <Edit2 className="w-3 h-3 text-slate-500" />
                            </button>
                            <button
                              onClick={() => deleteSub(sub.id)}
                              className="p-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                            >
                              <Trash2 className="w-3 h-3 text-red-500" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">
                      No subcategories yet
                    </p>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Category Modal */}
      <Modal
        isOpen={showCatModal}
        onClose={() => setShowCatModal(false)}
        title={editingCat ? "Edit Category" : "New Category"}
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Name *
            </label>
            <input
              type="text"
              value={catName}
              onChange={(e) => setCatName(e.target.value)}
              placeholder="Category name"
              className="input-field"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Description
            </label>
            <textarea
              value={catDescription}
              onChange={(e) => setCatDescription(e.target.value)}
              placeholder="Optional description"
              rows={3}
              className="input-field"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setShowCatModal(false)}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              onClick={saveCat}
              disabled={catSaving || !catName.trim()}
              className="btn-primary"
            >
              {catSaving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Subcategory Modal */}
      <Modal
        isOpen={showSubModal}
        onClose={() => setShowSubModal(false)}
        title={editingSubId ? "Edit Subcategory" : "New Subcategory"}
        size="sm"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Name *
            </label>
            <input
              type="text"
              value={subName}
              onChange={(e) => setSubName(e.target.value)}
              placeholder="Subcategory name"
              className="input-field"
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setShowSubModal(false)}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              onClick={saveSub}
              disabled={subSaving || !subName.trim()}
              className="btn-primary"
            >
              {subSaving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
