"use client";

import { AlertTriangle, Loader2, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { PageShell, QueryState } from "@/components/studio/PageShell";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { Button } from "@/components/ui/Button";
import {
  Badge,
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/primitives";
import { relativeTime } from "@/lib/relative-time";
import {
  deleteRedirect,
  listRedirects,
  saveRedirect,
  type RedirectRow,
} from "@/lib/studio-api";

export default function SeoPage() {
  const [editing, setEditing] = useState<RedirectRow | "new" | null>(null);
  const { data, loading, error, refresh } = useStudioQuery(() => listRedirects(), []);
  const rows = useMemo(() => data?.results ?? [], [data]);

  const problems = useMemo(() => findProblems(rows), [rows]);

  return (
    <PageShell
      title="SEO"
      description="Redirects keep old addresses working after a slug or category changes. Every rule here is served to the front end and applied before the page renders."
      actions={
        <Button size="sm" onClick={() => setEditing("new")}>
          <Plus size={14} /> New redirect
        </Button>
      }
    >
      {problems.length > 0 && (
        <div className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
          <p className="flex items-center gap-2 text-sm font-semibold text-amber-900 dark:text-amber-200">
            <AlertTriangle size={15} />
            {problems.length} rule{problems.length === 1 ? "" : "s"} will not behave
            as written
          </p>
          <ul className="mt-2 space-y-1 text-sm text-amber-900 dark:text-amber-300">
            {problems.map((problem) => (
              <li key={problem.path}>
                <code className="text-xs">{problem.path}</code> — {problem.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      <QueryState
        loading={loading}
        error={error}
        isEmpty={rows.length === 0}
        empty="No redirects yet. They are created automatically when you change a slug or move a category, and can be added by hand here."
      >
        <div className="overflow-x-auto rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-[var(--sl-line)] text-left text-xs uppercase tracking-wide text-[var(--sl-muted)]">
              <tr>
                <th className="px-4 py-2.5 font-medium">From</th>
                <th className="px-4 py-2.5 font-medium">To</th>
                <th className="px-4 py-2.5 font-medium">Code</th>
                <th className="px-4 py-2.5 text-right font-medium">Hits</th>
                <th className="px-4 py-2.5 font-medium">Last used</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--sl-line)]">
              {rows.map((row) => (
                <tr key={row.id} className={row.is_active ? "" : "opacity-50"}>
                  <td className="max-w-xs truncate px-4 py-2.5 font-mono text-xs">
                    {row.source_path}
                    {row.is_regex && (
                      <Badge tone="purple" className="ml-2">
                        regex
                      </Badge>
                    )}
                  </td>
                  <td className="max-w-xs truncate px-4 py-2.5 font-mono text-xs text-[var(--sl-muted)]">
                    {row.target_path}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone={row.status_code === 301 ? "green" : "slate"}>
                      {row.status_code}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-[var(--sl-muted)]">
                    {row.hit_count}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-[var(--sl-muted)]">
                    {row.last_hit_at ? relativeTime(row.last_hit_at) : "never"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Button size="sm" variant="ghost" onClick={() => setEditing(row)}>
                      Edit
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </QueryState>

      {editing && (
        <RedirectDialog
          redirect={editing === "new" ? null : editing}
          existing={rows}
          onClose={(changed) => {
            setEditing(null);
            if (changed) refresh();
          }}
        />
      )}
    </PageShell>
  );
}

/**
 * Rules that are broken in a way the server cannot see.
 *
 * The database enforces one rule per source path and nothing more, so the two
 * failures that actually strand visitors both get through: a rule pointing at
 * itself, and a chain that loops back to its own start. Both render as a
 * browser redirect loop with no error anywhere in the logs, which is why this
 * is checked here rather than left to be discovered.
 */
function findProblems(rows: RedirectRow[]) {
  const active = rows.filter((row) => row.is_active && !row.is_regex);
  const bySource = new Map(active.map((row) => [row.source_path, row.target_path]));
  const problems: Array<{ path: string; reason: string }> = [];

  for (const row of active) {
    if (row.source_path === row.target_path) {
      problems.push({ path: row.source_path, reason: "points at itself." });
      continue;
    }
    const seen = new Set([row.source_path]);
    let current = row.target_path;
    let hops = 0;
    while (bySource.has(current) && hops < 20) {
      if (seen.has(current)) {
        problems.push({
          path: row.source_path,
          reason: `loops back through ${current}.`,
        });
        break;
      }
      seen.add(current);
      current = bySource.get(current)!;
      hops += 1;
    }
    // Not an error, but each hop is a full round trip and search engines stop
    // following after a handful.
    if (hops >= 3) {
      problems.push({
        path: row.source_path,
        reason: `redirects ${hops} times before landing.`,
      });
    }
  }
  return problems;
}

function RedirectDialog({
  redirect,
  existing,
  onClose,
}: {
  redirect: RedirectRow | null;
  existing: RedirectRow[];
  onClose: (changed: boolean) => void;
}) {
  const [source, setSource] = useState(redirect?.source_path ?? "");
  const [target, setTarget] = useState(redirect?.target_path ?? "");
  const [code, setCode] = useState<RedirectRow["status_code"]>(
    redirect?.status_code ?? 301,
  );
  const [isActive, setIsActive] = useState(redirect?.is_active ?? true);
  const [note, setNote] = useState(redirect?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clash = existing.find(
    (row) => row.source_path === normalise(source) && row.id !== redirect?.id,
  );
  const selfLoop = normalise(source) === normalise(target) && source !== "";

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await saveRedirect(redirect?.id ?? null, {
        source_path: source,
        target_path: target,
        status_code: code,
        is_active: isActive,
        note,
      });
      onClose(true);
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, string[]> } }).response
        ?.data;
      setError(
        data ? Object.values(data).flat().join(" ") : "Could not save this redirect.",
      );
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!redirect) return;
    setBusy(true);
    await deleteRedirect(redirect.id);
    onClose(true);
  };

  return (
    <Dialog open onOpenChange={() => onClose(false)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{redirect ? "Edit redirect" : "New redirect"}</DialogTitle>
          <DialogDescription>
            Paths only, with a leading slash — the host is whichever site this
            rule belongs to.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">From</span>
            <input
              className="input-field font-mono text-sm"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="/articles/old-slug"
              autoFocus
            />
            {clash && (
              <span className="mt-1 block text-xs text-amber-600">
                A rule for this path already exists (→ {clash.target_path}). Saving
                will be rejected; edit that one instead.
              </span>
            )}
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">To</span>
            <input
              className="input-field font-mono text-sm"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="/articles/new-slug"
            />
            {selfLoop && (
              <span className="mt-1 block text-xs text-red-600">
                Source and target are the same — this is an infinite redirect.
              </span>
            )}
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">Type</span>
            <select
              className="input-field"
              value={code}
              onChange={(e) =>
                setCode(Number(e.target.value) as RedirectRow["status_code"])
              }
            >
              <option value={301}>301 — permanent (passes ranking)</option>
              <option value={302}>302 — temporary</option>
              <option value={307}>307 — temporary, keeps the method</option>
              <option value={308}>308 — permanent, keeps the method</option>
            </select>
            <span className="mt-1 block text-xs text-[var(--sl-muted)]">
              Use 301 for a renamed page. A 302 tells search engines the old URL
              is still the real one, so rankings stay on a page that no longer
              exists.
            </span>
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">Note</span>
            <input
              className="input-field"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Why this exists"
            />
          </label>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Active
          </label>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </DialogBody>

        <DialogFooter>
          {redirect && (
            <Button
              variant="ghost"
              className="mr-auto text-red-600"
              onClick={remove}
              disabled={busy}
            >
              <Trash2 size={14} /> Delete
            </Button>
          )}
          <Button variant="secondary" onClick={() => onClose(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || selfLoop || !source || !target}>
            {busy && <Loader2 size={14} className="animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function normalise(path: string) {
  const trimmed = path.trim();
  if (!trimmed || trimmed.startsWith("http")) return trimmed;
  return `/${trimmed.replace(/^\/+/, "").replace(/\/+$/, "")}`;
}
