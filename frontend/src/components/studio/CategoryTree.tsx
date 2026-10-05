"use client";

import {
  ChevronDown,
  ChevronRight,
  CornerDownRight,
  FolderTree,
  GripVertical,
  Plus,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { moveCategory, type CategoryNode, type MovedPath } from "@/lib/studio-api";

/**
 * Drag-to-reparent category tree.
 *
 * Two drop targets per row, not one. Dropping *onto* a row means "become its
 * child"; dropping onto the thin strip *between* rows means "become its
 * sibling, here". With only the first, there is no gesture for "promote this
 * back to a root", and the editor has to go through a form to undo a drag.
 *
 * HTML5 drag-and-drop rather than a library: the interaction is a few dozen
 * lines, it is keyboard-reachable through the explicit move buttons beside it,
 * and pulling in dnd-kit for one screen costs more bundle than the studio
 * spends on the editor itself.
 */

interface DropTarget {
  id: number | null;
  mode: "inside" | "before";
}

export function CategoryTree({
  tree,
  selected,
  onSelect,
  onMoved,
  onCreateChild,
}: {
  tree: CategoryNode[];
  selected: CategoryNode | null;
  onSelect: (node: CategoryNode) => void;
  onMoved: (changed: MovedPath[]) => void;
  onCreateChild: (parent: CategoryNode | null) => void;
}) {
  const [dragging, setDragging] = useState<CategoryNode | null>(null);
  const [over, setOver] = useState<DropTarget | null>(null);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const toggle = (id: number) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const drop = async (target: DropTarget) => {
    const node = dragging;
    setDragging(null);
    setOver(null);
    if (!node) return;

    const parent =
      target.mode === "inside" ? target.id : findParentId(tree, target.id);
    if (parent === node.id || parent === node.parent) return;

    setBusy(true);
    setError(null);
    try {
      const { changed_paths } = await moveCategory(node.slug, parent);
      onMoved(changed_paths);
    } catch (err: unknown) {
      const response = (err as { response?: { data?: { detail?: string } } }).response;
      // 409 here is a refused move (cycle, or too deep), not a transport
      // failure -- the server's sentence is the useful one.
      setError(response?.data?.detail ?? "That move was refused.");
    } finally {
      setBusy(false);
    }
  };

  const renderNode = (node: CategoryNode) => {
    const hasChildren = node.children.length > 0;
    const isCollapsed = collapsed.has(node.id);
    const isDropInside = over?.mode === "inside" && over.id === node.id;
    const isDropBefore = over?.mode === "before" && over.id === node.id;

    return (
      <li key={node.id}>
        <div
          aria-hidden="true"
          onDragOver={(e) => {
            e.preventDefault();
            setOver({ id: node.id, mode: "before" });
          }}
          onDrop={(e) => {
            e.preventDefault();
            drop({ id: node.id, mode: "before" });
          }}
          className={cn(
            "h-1.5 rounded-full transition-colors",
            isDropBefore && "bg-[var(--sl-soft)]",
          )}
        />
        <div
          draggable={!busy}
          onDragStart={() => setDragging(node)}
          onDragEnd={() => {
            setDragging(null);
            setOver(null);
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setOver({ id: node.id, mode: "inside" });
          }}
          onDrop={(e) => {
            e.preventDefault();
            drop({ id: node.id, mode: "inside" });
          }}
          onClick={() => onSelect(node)}
          className={cn(
            "group flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm transition-colors",
            selected?.id === node.id
              ? "bg-[var(--sl-soft)] text-[var(--sl-accent)] dark:bg-primary-950/50"
              : "hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]",
            isDropInside && "ring-2 ring-primary-500",
            dragging?.id === node.id && "opacity-40",
          )}
        >
          <GripVertical
            size={13}
            className="shrink-0 cursor-grab text-[var(--sl-muted)] group-hover:text-[var(--sl-muted)]"
          />
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggle(node.id);
              }}
              aria-label={isCollapsed ? "Expand" : "Collapse"}
              className="shrink-0 hover:text-[var(--sl-ink)]"
            >
              {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
            </button>
          ) : (
            <span className="w-[14px] shrink-0" />
          )}

          <span className="min-w-0 flex-1 truncate font-medium">{node.name}</span>

          {typeof node.article_count === "number" && node.article_count > 0 && (
            <span className="shrink-0 rounded bg-[var(--sl-soft)] px-1.5 text-xs tabular-nums text-[var(--sl-muted)] bg-[var(--sl-card)]">
              {node.article_count}
            </span>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onCreateChild(node);
            }}
            title={`Add a category under ${node.name}`}
            className="shrink-0 rounded p-0.5 opacity-0 transition hover:bg-[var(--sl-soft)] hover:text-[var(--sl-ink)] group-hover:opacity-100"
          >
            <CornerDownRight size={13} />
          </button>
        </div>

        {hasChildren && !isCollapsed && (
          <ul className="ml-4 border-l border-[var(--sl-line)] pl-2">
            {node.children.map(renderNode)}
          </ul>
        )}
      </li>
    );
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
          <FolderTree size={13} /> Tree
        </span>
        <Button size="sm" variant="ghost" onClick={() => onCreateChild(null)}>
          <Plus size={13} /> Root
        </Button>
      </div>

      {error && (
        <p className="mb-2 rounded-md bg-red-50 px-2.5 py-1.5 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      <ul>{tree.map(renderNode)}</ul>

      {/* The only gesture for "make this a root again". Without it, a category
          dragged into a parent by mistake can only be rescued through a form. */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver({ id: null, mode: "inside" });
        }}
        onDrop={(e) => {
          e.preventDefault();
          drop({ id: null, mode: "inside" });
        }}
        className={cn(
          "mt-3 rounded-lg border border-dashed border-[var(--sl-line)] py-3 text-center text-xs text-[var(--sl-muted)] transition",
          over?.id === null && over.mode === "inside" && "border-[var(--sl-soft)] text-[var(--sl-accent)]",
          !dragging && "opacity-50",
        )}
      >
        Drop here to make it a top-level category
      </div>
    </div>
  );
}

function findParentId(tree: CategoryNode[], id: number | null): number | null {
  if (id === null) return null;
  const walk = (nodes: CategoryNode[]): number | null | undefined => {
    for (const node of nodes) {
      if (node.id === id) return node.parent;
      const found = walk(node.children);
      if (found !== undefined) return found;
    }
    return undefined;
  };
  return walk(tree) ?? null;
}
