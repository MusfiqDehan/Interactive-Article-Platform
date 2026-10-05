"use client";

import { AlertTriangle, Clock, Loader2, Send, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { SocialPreview } from "@/components/studio/SocialPreview";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { countedLength } from "@/lib/graphemes";
import {
  createSocialPost,
  deriveCaptions,
  getPlatformSpecs,
  listSocialAccounts,
  type Platform,
  type SocialPost,
} from "@/lib/studio-api";

/**
 * Two-column composer: compose left, faithful previews right.
 *
 * The counters read their limits from `/social/platform-specs/` rather than
 * from constants here. That endpoint serves the same table the server
 * validates against, so "the composer said it fits and the platform truncated
 * it" cannot happen through a stale copy — which is the failure mode a
 * duplicated constant guarantees eventually.
 */
export function SocialComposer({
  articleId,
  articleTitle,
  onPublished,
}: {
  articleId?: number;
  articleTitle?: string;
  onPublished?: (post: SocialPost) => void;
}) {
  const { data: specs } = useStudioQuery(getPlatformSpecs, []);
  const { data: accounts, loading } = useStudioQuery(listSocialAccounts, []);

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [captions, setCaptions] = useState<Record<number, string>>({});
  const [active, setActive] = useState<number | null>(null);
  const [scheduleAt, setScheduleAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SocialPost | null>(null);

  const specByKey = useMemo(
    () => Object.fromEntries((specs ?? []).map((spec) => [spec.key, spec])),
    [specs],
  );
  const usable = (accounts ?? []).filter((account) => account.is_usable);
  const activeAccount =
    usable.find((account) => account.id === active) ??
    usable.find((account) => selected.has(account.id)) ??
    null;

  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else {
      next.add(id);
      setActive(id);
    }
    setSelected(next);
  };

  const suggest = async () => {
    if (!articleId) return;
    setBusy(true);
    setError(null);
    try {
      const platforms = Array.from(
        new Set(
          usable
            .filter((account) => selected.has(account.id))
            .map((account) => account.platform),
        ),
      );
      const previews = await deriveCaptions({ article: articleId, platforms });
      const byPlatform = Object.fromEntries(previews.map((p) => [p.platform, p]));
      const next = { ...captions };
      for (const account of usable) {
        if (!selected.has(account.id)) continue;
        // Only fill what is empty. Overwriting a caption someone wrote is the
        // one thing an "improve this" button must never do.
        if (!next[account.id]?.trim()) {
          next[account.id] = byPlatform[account.platform]?.caption ?? "";
        }
      }
      setCaptions(next);
      const impossible = previews.filter((p) => !p.fits);
      if (impossible.length) {
        setError(
          `Too long for ${impossible.map((p) => p.platform).join(", ")} even with the ` +
            "excerpt removed — shorten the title or drop a hashtag.",
        );
      }
    } catch {
      setError("Could not generate captions.");
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const post = await createSocialPost({
        article: articleId ?? null,
        scheduled_at: scheduleAt ? new Date(scheduleAt).toISOString() : null,
        targets: usable
          .filter((account) => selected.has(account.id))
          .map((account) => ({
            account: account.id,
            caption: captions[account.id] ?? "",
          })),
      });
      setResult(post);
      onPublished?.(post);
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, string[]> } }).response
        ?.data;
      setError(data ? Object.values(data).flat().join(" ") : "Could not submit.");
    } finally {
      setBusy(false);
    }
  };

  if (result) return <ResultStrip post={result} onReset={() => setResult(null)} />;

  if (loading) {
    return <p className="py-8 text-center text-sm text-[var(--sl-muted)]">Loading accounts…</p>;
  }
  if (usable.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--sl-line)] p-6 text-center text-sm text-[var(--sl-muted)]">
        No connected social accounts. Add one in Settings before composing.
      </p>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
            Post to
          </p>
          <div className="flex flex-wrap gap-1.5">
            {usable.map((account) => (
              <button
                key={account.id}
                onClick={() => toggle(account.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition",
                  selected.has(account.id)
                    ? "border-[var(--sl-soft)] bg-[var(--sl-action)] text-white"
                    : "border-[var(--sl-line)] text-[var(--sl-ink)] hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]",
                )}
              >
                {specByKey[account.platform]?.label ?? account.platform}
                <span className="opacity-70">{account.handle || account.display_name}</span>
              </button>
            ))}
          </div>
        </div>

        {selected.size > 0 && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex flex-wrap gap-1">
                {usable
                  .filter((a) => selected.has(a.id))
                  .map((account) => (
                    <button
                      key={account.id}
                      onClick={() => setActive(account.id)}
                      className={cn(
                        "rounded-md px-2.5 py-1 text-xs font-medium",
                        activeAccount?.id === account.id
                          ? "bg-[var(--sl-card)] text-white bg-[var(--sl-action)] text-[var(--sl-ink)]"
                          : "bg-[var(--sl-soft)] text-[var(--sl-ink)] bg-[var(--sl-card)]",
                      )}
                    >
                      {specByKey[account.platform]?.label ?? account.platform}
                    </button>
                  ))}
              </div>
              {articleId && (
                <Button size="sm" variant="secondary" onClick={suggest} disabled={busy}>
                  <Sparkles size={13} /> Suggest captions
                </Button>
              )}
            </div>

            {activeAccount && (
              <CaptionField
                key={activeAccount.id}
                value={captions[activeAccount.id] ?? ""}
                onChange={(value) =>
                  setCaptions((prev) => ({ ...prev, [activeAccount.id]: value }))
                }
                spec={specByKey[activeAccount.platform]}
              />
            )}

            <label className="block">
              <span className="mb-1 flex items-center gap-1.5 text-xs font-medium text-[var(--sl-muted)]">
                <Clock size={12} /> Schedule (optional)
              </span>
              <input
                type="datetime-local"
                className="input-field"
                value={scheduleAt}
                onChange={(e) => setScheduleAt(e.target.value)}
              />
              <span className="mt-1 block text-xs text-[var(--sl-muted)]">
                Held here and published at that moment by this CMS, not handed to
                the platform.
              </span>
            </label>
          </>
        )}

        {error && (
          <p className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            {error}
          </p>
        )}

        <Button
          onClick={submit}
          disabled={busy || selected.size === 0 || hasOverflow(usable, selected, captions, specByKey)}
        >
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          {scheduleAt ? "Schedule" : "Publish"} to {selected.size}
        </Button>
      </div>

      <div className="space-y-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--sl-muted)]">
          Preview
        </p>
        {usable
          .filter((account) => selected.has(account.id))
          .map((account) => (
            <SocialPreview
              key={account.id}
              platform={account.platform}
              caption={captions[account.id] || `Share “${articleTitle ?? "this article"}”…`}
              accountName={account.display_name}
              handle={account.handle}
              avatarUrl={account.avatar_url}
            />
          ))}
        {selected.size === 0 && (
          <p className="rounded-xl border border-dashed border-[var(--sl-line)] p-6 text-center text-sm text-[var(--sl-muted)]">
            Pick an account to see how the post will look.
          </p>
        )}
      </div>
    </div>
  );
}

function CaptionField({
  value,
  onChange,
  spec,
}: {
  value: string;
  onChange: (value: string) => void;
  spec?: { label: string; max_length: number; url_length: number | null; notes: string[] };
}) {
  if (!spec) return null;
  const used = countedLength(value, spec.url_length);
  const left = spec.max_length - used;

  return (
    <div>
      <textarea
        className="input-field h-40 resize-y"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`Write the ${spec.label} post…`}
      />
      <div className="mt-1 flex items-start justify-between gap-3 text-xs">
        <span className="text-[var(--sl-muted)]">{spec.notes[0]}</span>
        <span
          className={cn(
            "shrink-0 tabular-nums",
            left < 0 ? "font-semibold text-red-600" : left < 20 ? "text-amber-600" : "text-[var(--sl-muted)]",
          )}
        >
          {used}/{spec.max_length}
        </span>
      </div>
    </div>
  );
}

function hasOverflow(
  accounts: Array<{ id: number; platform: Platform }>,
  selected: Set<number>,
  captions: Record<number, string>,
  specs: Record<string, { max_length: number; url_length: number | null }>,
) {
  return accounts.some((account) => {
    if (!selected.has(account.id)) return false;
    const spec = specs[account.platform];
    if (!spec) return false;
    return countedLength(captions[account.id] ?? "", spec.url_length) > spec.max_length;
  });
}

/**
 * Per-target outcome after submitting.
 *
 * A single "posted!" toast would hide the one platform that refused, and the
 * editor would find out when someone asks why it never appeared.
 */
function ResultStrip({ post, onReset }: { post: SocialPost; onReset: () => void }) {
  return (
    <div className="space-y-3">
      <ul className="divide-y divide-[var(--sl-line)] rounded-xl border border-[var(--sl-line)]">
        {post.targets.map((target) => (
          <li key={target.id} className="flex items-start gap-3 px-4 py-3 text-sm">
            <span className="w-20 shrink-0 font-medium capitalize">{target.platform}</span>
            {target.state === "published" ? (
              <span className="flex-1 text-emerald-700 dark:text-emerald-400">
                Published{" "}
                {target.external_url && (
                  <a
                    href={target.external_url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    view post
                  </a>
                )}
              </span>
            ) : target.state === "failed" ? (
              <span className="flex-1 text-red-600">
                {target.last_error || "Failed."}
              </span>
            ) : target.state === "retrying" ? (
              <span className="flex-1 text-amber-600">
                Retrying — {target.last_error || "the platform is still working."}
              </span>
            ) : (
              <span className="flex-1 text-[var(--sl-muted)]">
                {post.state === "scheduled" ? "Scheduled." : "Sending…"}
              </span>
            )}
          </li>
        ))}
      </ul>
      <Button size="sm" variant="secondary" onClick={onReset}>
        Compose another
      </Button>
    </div>
  );
}
