"use client";

import type { OutputData } from "@editorjs/editorjs";
import { AlertTriangle, ArrowLeft, Check, ChevronDown, ExternalLink, History, Loader2 } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ArticleDeliveries } from "@/components/studio/ArticleDeliveries";
import { SeoPanel } from "@/components/studio/SeoPanel";
import { SocialComposer } from "@/components/studio/SocialComposer";
import { TagInput } from "@/components/studio/TagInput";
import { StatusBadge } from "@/components/studio/StatusBadge";
import { VisibilityControl } from "@/components/studio/VisibilityControl";
import { useAutosave } from "@/components/studio/useAutosave";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/primitives";
import { normalizeSlug } from "@/lib/slug";
import {
  getArticle,
  listRevisions,
  restoreRevision,
  runTransition,
  type AvailableTransition,
  type RevisionRow,
  type StudioArticle,
} from "@/lib/studio-api";

const Editor = dynamic(() => import("@/components/editor/Editor"), { ssr: false });

/**
 * Three-pane article editor: outline, canvas, right rail.
 *
 * The status here is never written directly -- publication moves through the
 * transition endpoint, so the split action button below offers exactly the
 * transitions the backend says this user may run, rather than a status dropdown
 * that can propose illegal moves and only discover them on save.
 */
export default function StudioArticleEditor() {
  const params = useParams();
  const slug = normalizeSlug(String(params.slug ?? ""));

  const [article, setArticle] = useState<StudioArticle | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [blocks, setBlocks] = useState<OutputData | undefined>(undefined);
  const [revisions, setRevisions] = useState<RevisionRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [editorEpoch, setEditorEpoch] = useState(0);

  const { state, queue, saveNow, keepMine, markVersion } = useAutosave(
    slug,
    article?.content_hash ?? null,
  );

  useEffect(() => {
    let cancelled = false;
    setArticle(null);
    setBlocks(undefined);
    setLoadError(null);
    getArticle(slug)
      .then((loaded) => {
        if (cancelled) return;
        setArticle(loaded);
        setTitle(loaded.title);
        setExcerpt(loaded.excerpt);
        setTags((loaded.tags ?? []).map((tag) => tag.name));
        // Only now is `blocks` defined, which is what unblocks Editor mounting.
        setBlocks((loaded.content as OutputData) ?? { blocks: [] });
      })
      .catch(() => {
        if (!cancelled) setLoadError("Could not load this article.");
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const refreshRevisions = useCallback(() => {
    listRevisions(slug)
      .then(setRevisions)
      .catch(() => setRevisions([]));
  }, [slug]);

  useEffect(refreshRevisions, [refreshRevisions]);

  const onEditorChange = useCallback(
    (data: OutputData) => {
      setBlocks(data);
      queue({ content: { blocks: data.blocks } as StudioArticle["content"] });
    },
    [queue],
  );

  /** Outline derived live from header blocks, so it tracks unsaved edits. */
  const outline = useMemo(() => {
    const list = (blocks?.blocks ?? []) as Array<{
      type: string;
      data?: { text?: string; level?: number };
    }>;
    return list
      .filter((block) => block.type === "header")
      .map((block) => ({
        text: (block.data?.text ?? "").replace(/<[^>]+>/g, ""),
        level: block.data?.level ?? 2,
      }));
  }, [blocks]);

  const wordCount = useMemo(() => {
    const list = (blocks?.blocks ?? []) as Array<{ data?: Record<string, unknown> }>;
    const text = list
      .map((block) => String(block.data?.text ?? ""))
      .join(" ")
      .replace(/<[^>]+>/g, " ");
    return text.split(/\s+/).filter(Boolean).length;
  }, [blocks]);

  const runAction = async (transition: AvailableTransition) => {
    setBusy(true);
    try {
      // Flush pending edits first: publishing content the server has not
      // received yet would put a stale version live.
      await saveNow();
      const result = await runTransition(slug, transition.name);
      setArticle(result.article);
      markVersion(result.article.content_hash);
      refreshRevisions();
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      alert(
        status === 409
          ? "That action is no longer valid — the article's state changed. Reload to see where it is now."
          : status === 403
            ? "You do not have permission to do that."
            : "Something went wrong.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (loadError) {
    return <p className="p-10 text-center text-sm text-red-600">{loadError}</p>;
  }

  if (!article) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="animate-spin text-[var(--sl-muted)]" />
      </div>
    );
  }

  const transitions = article.available_transitions ?? [];
  const primary = transitions[0];
  const rest = transitions.slice(1);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] min-w-0 flex-col">
      {/* Topbar */}
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-[var(--sl-line)] bg-[var(--sl-card)] px-4 py-2.5">
        <Button variant="ghost" size="icon" asChild aria-label="Back to content">
          <Link href="/studio/content">
            <ArrowLeft size={17} />
          </Link>
        </Button>

        <input
          value={title}
          onChange={(event) => {
            setTitle(event.target.value);
            queue({ title: event.target.value });
          }}
          placeholder="Untitled article"
          aria-label="Article title"
          className="min-w-0 flex-1 border-0 bg-transparent font-display text-lg font-bold text-[var(--sl-ink)] outline-none placeholder:text-[var(--sl-muted)]"
        />

        <StatusBadge status={article.status} />
        <VisibilityControl
          status={article.status}
          transitions={transitions}
          busy={busy}
          onRun={(name) => {
            const match = transitions.find((item) => item.name === name);
            if (match) void runAction(match);
          }}
        />
        <SaveIndicator state={state} onKeepMine={keepMine} />

        {article.is_live && article.placements?.[0]?.url && (
          <Button variant="ghost" size="sm" asChild>
            <a href={article.placements[0].url} target="_blank" rel="noreferrer">
              View <ExternalLink size={13} />
            </a>
          </Button>
        )}

        {/* Split action: primary is the next transition *for this role*, which
            is why an author sees "Submit for review" where an editor sees
            "Publish" without any client-side role logic. */}
        {primary ? (
          <div className="flex items-center">
            <Button
              disabled={busy}
              onClick={() => runAction(primary)}
              className={rest.length ? "rounded-r-none" : undefined}
            >
              {busy ? <Loader2 size={15} className="animate-spin" /> : null}
              {primary.label}
            </Button>
            {rest.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    disabled={busy}
                    className="rounded-l-none border-l border-[var(--sl-soft)] px-2"
                    aria-label="More actions"
                  >
                    <ChevronDown size={15} />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {rest.map((transition) => (
                    <DropdownMenuItem
                      key={transition.name}
                      onSelect={() => runAction(transition)}
                      destructive={transition.name === "archive"}
                    >
                      {transition.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        ) : (
          <span className="text-xs text-[var(--sl-muted)]">No actions available</span>
        )}
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Outline */}
        <aside className="relative z-0 hidden w-52 shrink-0 overflow-y-auto border-r border-[var(--sl-line)] bg-[var(--sl-card)] p-4 xl:block">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
            Outline
          </h2>
          {outline.length === 0 ? (
            <p className="text-xs text-[var(--sl-muted)]">Headings appear here.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {outline.map((heading, index) => (
                <li
                  key={index}
                  style={{ paddingLeft: `${(heading.level - 2) * 10}px` }}
                  className="truncate text-[var(--sl-ink)]"
                  title={heading.text}
                >
                  {heading.text || "(empty heading)"}
                </li>
              ))}
            </ul>
          )}

          <dl className="mt-6 space-y-1 border-t border-[var(--sl-line)] pt-4 text-xs text-[var(--sl-muted)]">
            <div className="flex justify-between">
              <dt>Blocks</dt>
              <dd>{blocks?.blocks?.length ?? 0}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Words</dt>
              <dd>{wordCount.toLocaleString()}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Read time</dt>
              <dd>{Math.max(1, Math.ceil(wordCount / 200))} min</dd>
            </div>
          </dl>
        </aside>

        {/* Canvas */}
        <div className="relative z-20 min-w-0 flex-1 overflow-y-auto bg-[var(--sl-soft)] px-4 py-6 bg-[var(--sl-card)]">
          <div className="mx-auto max-w-3xl">
            {/* key remounts only when switching articles or restoring a
                revision. Autosave must not change this -- Editor.js cannot be
                updated in place, and recreating it on every keystroke makes
                the plus button and placeholder blink. */}
            <Editor
              key={`${slug}-${editorEpoch}`}
              holder="studio-editor"
              data={
                article && normalizeSlug(article.slug) === slug ? blocks : undefined
              }
              onChange={onEditorChange}
            />
          </div>
        </div>

        {/* Right rail */}
        <aside className="relative z-0 hidden w-80 shrink-0 overflow-y-auto border-l border-[var(--sl-line)] bg-[var(--sl-card)] lg:block">
          <Tabs defaultValue="settings">
            <TabsList className="w-full px-3">
              <TabsTrigger value="seo">SEO</TabsTrigger>
              <TabsTrigger value="settings">Settings</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
              <TabsTrigger value="distribute">Distribute</TabsTrigger>
            </TabsList>

            <TabsContent value="seo" className="p-4">
              <SeoPanel
                slug={slug}
                title={title}
                excerpt={excerpt}
                blocks={blocks}
                siteUrl={article.placements?.[0]?.url ?? ""}
              />
            </TabsContent>

            <TabsContent value="settings" className="space-y-4 p-4">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
                  Excerpt
                </span>
                <textarea
                  value={excerpt}
                  rows={4}
                  maxLength={500}
                  onChange={(event) => {
                    setExcerpt(event.target.value);
                    queue({ excerpt: event.target.value });
                  }}
                  className="input-field resize-y"
                />
                <span className="mt-1 block text-right text-xs text-[var(--sl-muted)]">
                  {excerpt.length}/500
                </span>
              </label>

              <div>
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
                  Tags
                </span>
                <TagInput
                  value={tags}
                  onChange={(next) => {
                    setTags(next);
                    // Sent as `tag_slugs`: the server resolves names it already
                    // knows and creates the rest, so a tag typed here needs no
                    // round trip through the taxonomy screen first.
                    queue({ tag_slugs: next } as Partial<StudioArticle>);
                  }}
                />
              </div>

              <dl className="space-y-2 border-t border-[var(--sl-line)] pt-4 text-sm">
                <Row label="Slug" value={article.slug} mono />
                <Row label="Author" value={article.author?.name ?? "—"} />
                <Row
                  label="First published"
                  value={
                    article.published_at
                      ? new Date(article.published_at).toLocaleString()
                      : "Never"
                  }
                />
                <Row
                  label="Last published"
                  value={
                    article.last_published_at
                      ? new Date(article.last_published_at).toLocaleString()
                      : "—"
                  }
                />
                {article.scheduled_publish_at && (
                  <Row
                    label="Scheduled"
                    value={new Date(article.scheduled_publish_at).toLocaleString()}
                  />
                )}
              </dl>
            </TabsContent>

            <TabsContent value="history" className="p-4">
              {revisions.length === 0 ? (
                <p className="text-sm text-[var(--sl-muted)]">No revisions yet.</p>
              ) : (
                <ul className="space-y-2">
                  {revisions.map((revision) => (
                    <li
                      key={revision.id}
                      className="rounded-lg border border-[var(--sl-line)] p-3 text-sm"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-[var(--sl-ink)]">
                          v{revision.number}
                        </span>
                        <button
                          onClick={async () => {
                            if (!confirm(`Restore v${revision.number}? Current content is snapshotted first.`)) return;
                            const updated = await restoreRevision(slug, revision.number);
                            setArticle(updated);
                            setTitle(updated.title);
                            setBlocks(updated.content as OutputData);
                            markVersion(updated.content_hash);
                            setEditorEpoch((epoch) => epoch + 1);
                            refreshRevisions();
                          }}
                          className="flex items-center gap-1 text-xs text-[var(--sl-accent)] hover:underline"
                        >
                          <History size={12} /> Restore
                        </button>
                      </div>
                      <p className="mt-0.5 text-xs text-[var(--sl-muted)]">
                        {revision.reason || "edit"} · {revision.created_by_name} ·{" "}
                        {new Date(revision.created_at).toLocaleString()}
                      </p>
                      <p className="text-xs text-[var(--sl-muted)]">
                        {revision.summary.blocks} blocks
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>

            <TabsContent value="distribute" className="p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
                Share
              </p>
              <SocialComposer articleId={article.id} articleTitle={article.title} />
              <div className="mt-6 border-t border-[var(--sl-line)] pt-5" />
              <ArticleDeliveries articleId={article.id} />
              <p className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
                Placements
              </p>
              <ul className="space-y-2">
                {(article.placements ?? []).map((placement) => (
                  <li
                    key={placement.id}
                    className="rounded-lg border border-[var(--sl-line)] p-3 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{placement.site_name}</span>
                      {placement.is_live ? (
                        <span className="flex items-center gap-1 text-xs text-emerald-600">
                          <Check size={12} /> Live
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--sl-muted)]">Not live</span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-[var(--sl-muted)]">{placement.url}</p>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-xs text-[var(--sl-muted)]">
                Adding destinations and delivery status arrives with syndication.
              </p>
            </TabsContent>
          </Tabs>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="shrink-0 text-[var(--sl-muted)]">{label}</dt>
      <dd
        className={`truncate text-right text-[var(--sl-ink)] text-[var(--sl-muted)] ${mono ? "font-mono text-xs" : ""}`}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}

function SaveIndicator({
  state,
  onKeepMine,
}: {
  state: ReturnType<typeof useAutosave>["state"];
  onKeepMine: () => void;
}) {
  if (state.kind === "conflict") {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-2.5 py-1 text-xs text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">
        <AlertTriangle size={13} />
        <span>Someone else edited this.</span>
        <button onClick={onKeepMine} className="font-semibold underline">
          Keep mine
        </button>
        <button onClick={() => window.location.reload()} className="font-semibold underline">
          Take theirs
        </button>
      </div>
    );
  }

  const text: Record<string, string> = {
    idle: "",
    dirty: "Unsaved changes",
    saving: "Saving…",
    saved: "Saved",
    error: "",
  };

  if (state.kind === "error") {
    return <span className="text-xs text-red-600">{state.message}</span>;
  }

  return (
    <span className="whitespace-nowrap text-xs text-[var(--sl-muted)]">{text[state.kind]}</span>
  );
}
