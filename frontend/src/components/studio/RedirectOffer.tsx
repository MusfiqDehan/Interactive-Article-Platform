"use client";

import { Check, Loader2, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/primitives";
import { saveRedirect, type MovedPath } from "@/lib/studio-api";

/**
 * Offers 301s for URLs that a category move just broke.
 *
 * This appears immediately after the move and not as a later chore, because
 * the old path only exists in the response to that one request. Close this
 * without acting and the information is gone -- the category no longer knows
 * where it used to live, and the only remaining record is in visitors' 404s.
 *
 * Checked by default: the move already happened, those URLs are already
 * broken, and the redirect is the strictly better outcome. Opting out is for
 * the case where the old path was never public.
 */
export function RedirectOffer({
  changed,
  onClose,
}: {
  changed: MovedPath[];
  onClose: () => void;
}) {
  const [chosen, setChosen] = useState<Set<number> | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState<{ created: number; failed: string[] } | null>(null);

  if (changed.length === 0) return null;
  const selected = chosen ?? new Set(changed.map((row) => row.id));

  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChosen(next);
  };

  const create = async () => {
    setSaving(true);
    const failed: string[] = [];
    let created = 0;
    for (const row of changed) {
      if (!selected.has(row.id)) continue;
      try {
        await saveRedirect(null, {
          source_path: `/categories/${row.from}`,
          target_path: `/categories/${row.to}`,
          status_code: 301,
          note: `Category "${row.name}" moved`,
        });
        created += 1;
      } catch {
        // A duplicate source_path is the common failure and a benign one --
        // a redirect for that path already exists. Reported, not swallowed.
        failed.push(row.from);
      }
    }
    setDone({ created, failed });
    setSaving(false);
  };

  const close = () => {
    setChosen(null);
    setDone(null);
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {done ? "Redirects created" : `${changed.length} URL${changed.length === 1 ? "" : "s"} changed`}
          </DialogTitle>
          <DialogDescription>
            {done
              ? `${done.created} created${done.failed.length ? `, ${done.failed.length} skipped` : ""}.`
              : "These addresses stopped working when you moved the category. Add 301s so existing links and search rankings survive."}
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          {done ? (
            done.failed.length > 0 ? (
              <ul className="space-y-1 text-sm">
                {done.failed.map((path) => (
                  <li key={path} className="flex items-start gap-2 text-amber-700 dark:text-amber-400">
                    <X size={14} className="mt-0.5 shrink-0" />
                    <span>
                      <code className="text-xs">/{path}</code> — a redirect for
                      this path already exists.
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
                <Check size={15} /> Every changed URL now redirects.
              </p>
            )
          ) : (
            <ul className="divide-y divide-[var(--sl-line)] rounded-lg border border-[var(--sl-line)]">
              {changed.map((row) => (
                <li key={row.id} className="flex items-start gap-2.5 px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={selected.has(row.id)}
                    onChange={() => toggle(row.id)}
                    className="mt-1"
                    aria-label={`Redirect for ${row.name}`}
                  />
                  <span className="min-w-0 flex-1 text-sm">
                    <span className="block font-medium text-[var(--sl-ink)]">
                      {row.name}
                    </span>
                    <span className="block truncate font-mono text-xs text-[var(--sl-muted)]">
                      /{row.from} → /{row.to}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </DialogBody>

        <DialogFooter>
          {done ? (
            <Button onClick={close}>Done</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={close}>
                Skip
              </Button>
              <Button onClick={create} disabled={saving || selected.size === 0}>
                {saving && <Loader2 size={14} className="animate-spin" />}
                Create {selected.size} redirect{selected.size === 1 ? "" : "s"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
