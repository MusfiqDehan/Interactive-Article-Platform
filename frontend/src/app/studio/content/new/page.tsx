"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { createArticle } from "@/lib/studio-api";

/**
 * Create, then redirect into the full editor.
 *
 * Deliberately just a title: the article needs to exist server-side before
 * autosave has anything to PATCH against, and the slug it comes back with is
 * what the editor route is keyed on. Articles are always created as drafts --
 * `status` is not writable on either API surface.
 */
export default function NewArticlePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const article = await createArticle({
        title: title.trim(),
        content: { blocks: [] },
      });
      router.replace(`/studio/content/${encodeURIComponent(article.slug)}`);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(
        status === 403
          ? "You do not have permission to create articles on this site."
          : "Could not create the article.",
      );
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl p-10">
      <h1 className="mb-1 font-display text-2xl font-bold text-[var(--sl-ink)]">
        New article
      </h1>
      <p className="mb-6 text-sm text-[var(--sl-muted)]">
        Give it a working title. Everything else happens in the editor.
      </p>

      <form onSubmit={submit} className="card space-y-4 p-6">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-[var(--sl-ink)]">
            Title
          </span>
          <input
            autoFocus
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="How neural machine translation works"
            className="input-field"
            maxLength={300}
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => router.back()}>
            Cancel
          </Button>
          <Button type="submit" disabled={busy || !title.trim()}>
            {busy && <Loader2 size={15} className="animate-spin" />}
            Create draft
          </Button>
        </div>
      </form>
    </div>
  );
}
