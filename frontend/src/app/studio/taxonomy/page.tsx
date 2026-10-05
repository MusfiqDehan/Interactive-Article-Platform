"use client";

import { Loader2, Save, Trash2 } from "lucide-react";
import { useState } from "react";

import { CategoryTree } from "@/components/studio/CategoryTree";
import { PageShell, QueryState } from "@/components/studio/PageShell";
import { RedirectOffer } from "@/components/studio/RedirectOffer";
import { TagManager } from "@/components/studio/TagManager";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { Button } from "@/components/ui/Button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import {
  getCategoryTree,
  saveCategory,
  studioApi,
  type CategoryNode,
  type MovedPath,
} from "@/lib/studio-api";

export default function TaxonomyPage() {
  const { data: tree, loading, error, refresh } = useStudioQuery(getCategoryTree, []);
  // The *id* is the state; the node is looked up from the current tree on every
  // render. Storing the node object instead would mean the open form keeps
  // showing the name and url_path captured at click time -- stale the moment
  // anything is moved -- and "Save" would write that stale copy back. Syncing
  // it in an effect was the first version of this and is a cascading render for
  // a value that was always derivable.
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [pendingParent, setPendingParent] = useState<CategoryNode | null | undefined>();
  const [movedPaths, setMovedPaths] = useState<MovedPath[]>([]);

  const selected = tree && selectedId !== null ? findNode(tree, selectedId) : null;

  return (
    <PageShell
      title="Taxonomy"
      description="Categories are a tree — an article lives at one place in it. Tags cut across the tree and can be applied freely."
    >
      <Tabs defaultValue="categories">
        <TabsList>
          <TabsTrigger value="categories">Categories</TabsTrigger>
          <TabsTrigger value="tags">Tags</TabsTrigger>
        </TabsList>

        <TabsContent value="categories" className="mt-5">
          <QueryState
            loading={loading}
            error={error}
            isEmpty={(tree?.length ?? 0) === 0 && pendingParent === undefined}
            empty={
              <div className="space-y-3">
                <p>No categories yet.</p>
                <Button size="sm" onClick={() => setPendingParent(null)}>
                  Create the first one
                </Button>
              </div>
            }
          >
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
              <div className="rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-4">
                <CategoryTree
                  tree={tree ?? []}
                  selected={selected}
                  onSelect={(node) => {
                    setPendingParent(undefined);
                    setSelectedId(node.id);
                  }}
                  onCreateChild={(parent) => {
                    setSelectedId(null);
                    setPendingParent(parent);
                  }}
                  onMoved={(changed) => {
                    setMovedPaths(changed);
                    refresh();
                  }}
                />
              </div>

              <div>
                {pendingParent !== undefined ? (
                  <CategoryForm
                    key="new"
                    parent={pendingParent}
                    onDone={() => {
                      setPendingParent(undefined);
                      refresh();
                    }}
                    onCancel={() => setPendingParent(undefined)}
                  />
                ) : selected ? (
                  <CategoryForm
                    key={selected.id}
                    category={selected}
                    onDone={refresh}
                    onCancel={() => setSelectedId(null)}
                  />
                ) : (
                  <p className="rounded-xl border border-dashed border-[var(--sl-line)] p-6 text-center text-sm text-[var(--sl-muted)]">
                    Select a category to edit it, or drag one onto another to
                    reparent it.
                  </p>
                )}
              </div>
            </div>
          </QueryState>
        </TabsContent>

        <TabsContent value="tags" className="mt-5">
          <TagManager />
        </TabsContent>
      </Tabs>

      <RedirectOffer changed={movedPaths} onClose={() => setMovedPaths([])} />
    </PageShell>
  );
}

function CategoryForm({
  category,
  parent,
  onDone,
  onCancel,
}: {
  category?: CategoryNode;
  parent?: CategoryNode | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(category?.name ?? "");
  const [slug, setSlug] = useState(category?.slug ?? "");
  const [description, setDescription] = useState(category?.description ?? "");
  const [isActive, setIsActive] = useState(category?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slugChanged = Boolean(category && slug && slug !== category.slug);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await saveCategory(category?.slug ?? null, {
        name,
        description,
        is_active: isActive,
        ...(category ? {} : { parent: parent?.id ?? null }),
        ...(slugChanged ? { slug } : {}),
      });
      onDone();
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, string[]> } }).response
        ?.data;
      setError(
        data ? Object.values(data).flat().join(" ") : "Could not save this category.",
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!category) return;
    setSaving(true);
    setError(null);
    try {
      await studioApi().delete(`/categories/${encodeURIComponent(category.slug)}/`);
      onDone();
      onCancel();
    } catch (err: unknown) {
      const response = (err as { response?: { data?: { detail?: string } } }).response;
      setError(response?.data?.detail ?? "Could not delete this category.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="space-y-4 rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-5"
    >
      <h2 className="font-semibold text-[var(--sl-ink)]">
        {category ? "Edit category" : parent ? `New under ${parent.name}` : "New root category"}
      </h2>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">Name</span>
        <input
          className="input-field"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          autoFocus
        />
      </label>

      {category && (
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">Slug</span>
          <input
            className="input-field font-mono text-xs"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          />
          <span className="mt-1 block text-xs text-[var(--sl-muted)]">
            Currently at <code>/{category.url_path}</code>
          </span>
          {slugChanged && (
            // Stated before saving, not after: once the slug is written the old
            // URL is already 404ing, and this is the last moment anyone knows
            // what it was.
            <span className="mt-1 block text-xs text-amber-600 dark:text-amber-400">
              Changing this breaks every existing link to this category and its
              children. Add a redirect from <code>/{category.url_path}</code>{" "}
              afterwards.
            </span>
          )}
        </label>
      )}

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">Description</span>
        <textarea
          className="input-field h-24 resize-y"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>

      <label className="flex items-center gap-2 text-sm text-[var(--sl-ink)]">
        <input
          type="checkbox"
          checked={isActive}
          onChange={(e) => setIsActive(e.target.checked)}
        />
        Visible on the public site
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex items-center gap-2 pt-1">
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save
        </Button>
        <Button type="button" size="sm" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        {category && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="ml-auto text-red-600"
            onClick={remove}
            disabled={saving}
          >
            <Trash2 size={14} /> Delete
          </Button>
        )}
      </div>
    </form>
  );
}

function findNode(nodes: CategoryNode[], id: number): CategoryNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    const found = findNode(node.children, id);
    if (found) return found;
  }
  return null;
}
