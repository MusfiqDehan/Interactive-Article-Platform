"use client";

import { AlertTriangle, ExternalLink, Loader2, RotateCw } from "lucide-react";
import { useState } from "react";

import { PageShell, QueryState } from "@/components/studio/PageShell";
import { SocialComposer } from "@/components/studio/SocialComposer";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { Button } from "@/components/ui/Button";
import {
  Badge,
  type BadgeTone,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/primitives";
import { relativeTime } from "@/lib/relative-time";
import {
  listSocialAccounts,
  listSocialPosts,
  retrySocialTarget,
  type SocialTarget,
} from "@/lib/studio-api";

const TARGET_TONE: Record<SocialTarget["state"], BadgeTone> = {
  pending: "slate",
  publishing: "blue",
  retrying: "amber",
  published: "green",
  failed: "red",
  cancelled: "slate",
};

export default function SocialPage() {
  return (
    <PageShell
      title="Social"
      description="One submission, one post per platform — each with its own caption, its own state, and its own retry."
    >
      <Tabs defaultValue="compose">
        <TabsList>
          <TabsTrigger value="compose">Compose</TabsTrigger>
          <TabsTrigger value="posts">Posts</TabsTrigger>
          <TabsTrigger value="accounts">Accounts</TabsTrigger>
        </TabsList>

        <TabsContent value="compose" className="mt-5">
          <SocialComposer />
        </TabsContent>
        <TabsContent value="posts" className="mt-5">
          <Posts />
        </TabsContent>
        <TabsContent value="accounts" className="mt-5">
          <Accounts />
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}

function Posts() {
  const { data, loading, error, refresh } = useStudioQuery(() => listSocialPosts(), []);
  const rows = data?.results ?? [];

  return (
    <QueryState
      loading={loading}
      error={error}
      isEmpty={rows.length === 0}
      empty="Nothing posted yet."
    >
      <ul className="space-y-3">
        {rows.map((post) => (
          <li
            key={post.id}
            className="rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-4"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-[var(--sl-ink)]">
                {post.article_label || "Untitled share"}
              </span>
              <Badge
                tone={
                  post.state === "published"
                    ? "green"
                    : post.state === "partial"
                      ? "amber"
                      : post.state === "failed"
                        ? "red"
                        : "slate"
                }
              >
                {post.state}
              </Badge>
              <span className="text-xs text-[var(--sl-muted)]">
                {post.scheduled_at
                  ? `scheduled ${relativeTime(post.scheduled_at)}`
                  : relativeTime(post.created_at)}
              </span>
            </div>
            <TargetRows targets={post.targets} onChanged={refresh} />
          </li>
        ))}
      </ul>
    </QueryState>
  );
}

function TargetRows({
  targets,
  onChanged,
}: {
  targets: SocialTarget[];
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState<number | null>(null);

  return (
    <ul className="divide-y divide-[var(--sl-line)] rounded-lg border border-[var(--sl-line)]">
      {targets.map((target) => (
        <li key={target.id} className="flex flex-wrap items-center gap-2.5 px-3 py-2 text-sm">
          <span className="w-20 shrink-0 capitalize text-[var(--sl-ink)]">
            {target.platform}
          </span>
          <span className="min-w-0 flex-1 truncate text-[var(--sl-muted)]">
            {target.caption || "—"}
          </span>

          {target.state === "published" && target.metrics?.impressions != null && (
            <span className="shrink-0 text-xs tabular-nums text-[var(--sl-muted)]">
              {String(target.metrics.impressions)} impressions
            </span>
          )}

          <Badge tone={TARGET_TONE[target.state] ?? "slate"}>{target.state}</Badge>

          {target.external_url && (
            <a
              href={target.external_url}
              target="_blank"
              rel="noreferrer"
              className="flex shrink-0 items-center gap-1 text-xs text-[var(--sl-accent)] hover:underline"
            >
              view <ExternalLink size={11} />
            </a>
          )}

          {target.state !== "published" && (
            <Button
              size="sm"
              variant="ghost"
              disabled={busy === target.id}
              onClick={async () => {
                setBusy(target.id);
                try {
                  await retrySocialTarget(target.id);
                  onChanged();
                } finally {
                  setBusy(null);
                }
              }}
            >
              {busy === target.id ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <RotateCw size={13} />
              )}
              {/* Per target, not per post: re-sending the whole thing would
                  duplicate the platforms that already worked. */}
              Retry
            </Button>
          )}

          {target.last_error && (
            <p className="w-full text-xs text-red-600">{target.last_error}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

function Accounts() {
  const { data, loading, error } = useStudioQuery(listSocialAccounts, []);
  const rows = data ?? [];

  return (
    <QueryState
      loading={loading}
      error={error}
      isEmpty={rows.length === 0}
      empty="No social accounts connected."
    >
      <ul className="divide-y divide-[var(--sl-line)] rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
        {rows.map((account) => (
          <li key={account.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium text-[var(--sl-ink)]">
                {account.display_name}
              </span>
              <span className="block truncate text-xs text-[var(--sl-muted)]">
                {account.platform} · {account.handle || "no handle"} · via{" "}
                {account.provider}
              </span>
            </span>
            {account.is_usable ? (
              <Badge tone="green">connected</Badge>
            ) : (
              <span className="flex items-center gap-2">
                <Badge tone="red">
                  <AlertTriangle size={11} /> {account.status}
                </Badge>
                <span className="text-xs text-[var(--sl-muted)]">{account.status_detail}</span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </QueryState>
  );
}
