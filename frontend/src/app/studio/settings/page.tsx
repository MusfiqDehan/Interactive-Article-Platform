"use client";

import { Check, Copy, Key, Loader2, Plus, Save } from "lucide-react";
import { useEffect, useState } from "react";

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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/primitives";
import { relativeTime } from "@/lib/relative-time";
import {
  createApiKey,
  getSettings,
  listApiKeys,
  revokeApiKey,
  saveSettings,
  type ApiKeyRow,
  type SiteSettings,
} from "@/lib/studio-api";

export default function SettingsPage() {
  return (
    <PageShell
      title="Settings"
      description="Configuration for the site you are currently editing. Switch sites in the top bar to configure another."
    >
      <Tabs defaultValue="site">
        <TabsList>
          <TabsTrigger value="site">Site</TabsTrigger>
          <TabsTrigger value="keys">API keys</TabsTrigger>
        </TabsList>
        <TabsContent value="site" className="mt-5">
          <SiteSettingsForm />
        </TabsContent>
        <TabsContent value="keys" className="mt-5">
          <ApiKeys />
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}

function SiteSettingsForm() {
  const { data, loading, error, refresh } = useStudioQuery(getSettings, []);
  const [form, setForm] = useState<Partial<SiteSettings>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Seed the form once the fetch lands. Keyed on the fetched object so a
  // refresh after save re-seeds, but typing between renders is never clobbered.
  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const set = <K extends keyof SiteSettings>(key: K, value: SiteSettings[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      await saveSettings(form);
      setSaved(true);
      refresh();
    } catch (err: unknown) {
      const body = (err as { response?: { data?: Record<string, string[]> } }).response
        ?.data;
      setSaveError(
        body ? Object.values(body).flat().join(" ") : "Could not save these settings.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <QueryState loading={loading} error={error} isEmpty={false} empty={null}>
      <form onSubmit={submit} className="max-w-2xl space-y-5">
        <Field
          label="Site title"
          hint="Used in the browser tab, Open Graph cards and the Organization schema."
        >
          <input
            className="input-field"
            value={form.site_title ?? ""}
            onChange={(e) => set("site_title", e.target.value)}
          />
        </Field>

        <Field
          label="Title template"
          hint="%s is replaced by each page's own title. Every character here is spent on every page, and the pixel budget for a search result is about 600px."
        >
          <input
            className="input-field font-mono text-sm"
            value={form.title_template ?? ""}
            onChange={(e) => set("title_template", e.target.value)}
          />
        </Field>

        <Field
          label="Default meta description"
          hint="Used where a page has none of its own. A generic one repeated site-wide is worse than none — Google will write its own from the page instead."
        >
          <textarea
            className="input-field h-20 resize-y"
            value={form.default_meta_description ?? ""}
            onChange={(e) => set("default_meta_description", e.target.value)}
          />
          <span className="mt-1 block text-xs text-[var(--sl-muted)]">
            {(form.default_meta_description ?? "").length} characters
          </span>
        </Field>

        <Field
          label="Default social image"
          hint="An absolute URL. 1200×630 is what every platform crops toward."
        >
          <input
            className="input-field"
            value={form.default_og_image ?? ""}
            onChange={(e) => set("default_og_image", e.target.value)}
            placeholder="https://…"
          />
        </Field>

        <Field
          label="Google site verification"
          hint="The content value of the meta tag Search Console gives you."
        >
          <input
            className="input-field font-mono text-sm"
            value={form.google_site_verification ?? ""}
            onChange={(e) => set("google_site_verification", e.target.value)}
          />
        </Field>

        <Field
          label="robots.txt additions"
          hint="Appended to the generated robots.txt. Sitemap and host lines are added automatically."
        >
          <textarea
            className="input-field h-24 resize-y font-mono text-xs"
            value={form.robots_extra ?? ""}
            onChange={(e) => set("robots_extra", e.target.value)}
          />
        </Field>

        <label className="flex items-start gap-2 text-sm text-[var(--sl-ink)]">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={form.allow_ai_crawlers ?? true}
            onChange={(e) => set("allow_ai_crawlers", e.target.checked)}
          />
          <span>
            Allow AI crawlers
            <span className="block text-xs text-[var(--sl-muted)]">
              Unchecking adds GPTBot, CCBot and friends to robots.txt as
              disallowed. It does not affect Googlebot or search indexing.
            </span>
          </span>
        </label>

        <Field
          label="Revalidation endpoint"
          hint="Where a publish sends its cache-purge signal. Usually https://<your-site>/api/revalidate."
        >
          <input
            className="input-field font-mono text-sm"
            value={form.revalidate_url ?? ""}
            onChange={(e) => set("revalidate_url", e.target.value)}
          />
        </Field>

        {saveError && <p className="text-sm text-red-600">{saveError}</p>}

        <div className="flex items-center gap-3 border-t border-[var(--sl-line)] pt-4">
          <Button type="submit" disabled={saving}>
            {saving ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Save size={15} />
            )}
            Save settings
          </Button>
          {saved && (
            <span className="flex items-center gap-1 text-sm text-emerald-600">
              <Check size={14} /> Saved
            </span>
          )}
        </div>
      </form>
    </QueryState>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-[var(--sl-ink)]">
        {label}
      </span>
      {hint && <span className="mb-1.5 block text-xs text-[var(--sl-muted)]">{hint}</span>}
      {children}
    </label>
  );
}

function ApiKeys() {
  const { data, loading, error, refresh } = useStudioQuery(listApiKeys, []);
  const [creating, setCreating] = useState(false);
  const [minted, setMinted] = useState<ApiKeyRow | null>(null);

  return (
    <div>
      <div className="mb-4 flex items-start justify-between gap-3">
        <p className="max-w-xl text-sm text-[var(--sl-muted)]">
          Keys authenticate the public delivery API. Each one is bound to this
          site, so a deployed front end can only ever read the tenant it was
          issued for.
        </p>
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus size={14} /> New key
        </Button>
      </div>

      <QueryState
        loading={loading}
        error={error}
        isEmpty={(data ?? []).length === 0}
        empty="No API keys yet."
      >
        <ul className="divide-y divide-[var(--sl-line)] rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
          {(data ?? []).map((key) => (
            <li key={key.id} className="flex items-center gap-3 px-4 py-3">
              <Key size={15} className="shrink-0 text-[var(--sl-muted)]" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-[var(--sl-ink)]">
                  {key.name}
                </span>
                <span className="block font-mono text-xs text-[var(--sl-muted)]">
                  {key.prefix}…
                </span>
              </span>
              <span className="hidden text-xs text-[var(--sl-muted)] sm:block">
                {key.last_used_at
                  ? `used ${relativeTime(key.last_used_at)}`
                  : "never used"}
              </span>
              {key.revoked_at ? (
                <Badge tone="red">revoked</Badge>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-red-600"
                  onClick={async () => {
                    await revokeApiKey(key.id);
                    refresh();
                  }}
                >
                  Revoke
                </Button>
              )}
            </li>
          ))}
        </ul>
      </QueryState>

      {creating && (
        <NewKeyDialog
          onClose={(key) => {
            setCreating(false);
            if (key) {
              setMinted(key);
              refresh();
            }
          }}
        />
      )}
      {minted && <MintedKeyDialog apiKey={minted} onClose={() => setMinted(null)} />}
    </div>
  );
}

const SCOPES = [
  { value: "read:content", label: "Read articles" },
  { value: "read:taxonomy", label: "Read categories and tags" },
  { value: "read:media", label: "Read media" },
  { value: "write:events", label: "Write analytics events" },
];

function NewKeyDialog({ onClose }: { onClose: (key: ApiKeyRow | null) => void }) {
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["read:content", "read:taxonomy"]);
  const [busy, setBusy] = useState(false);

  return (
    <Dialog open onOpenChange={() => onClose(null)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New API key</DialogTitle>
          <DialogDescription>
            Grant only what the consumer needs — a key with fewer scopes is a
            smaller problem if it leaks.
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">
              Name it after where it will live
            </span>
            <input
              className="input-field"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Production front end"
              autoFocus
            />
          </label>
          <fieldset>
            <legend className="mb-2 text-xs font-medium text-[var(--sl-muted)]">Scopes</legend>
            <div className="space-y-1">
              {SCOPES.map((scope) => (
                <label key={scope.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={scopes.includes(scope.value)}
                    onChange={(e) =>
                      setScopes((prev) =>
                        e.target.checked
                          ? [...prev, scope.value]
                          : prev.filter((s) => s !== scope.value),
                      )
                    }
                  />
                  {scope.label}
                </label>
              ))}
            </div>
          </fieldset>
        </DialogBody>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onClose(null)}>
            Cancel
          </Button>
          <Button
            disabled={busy || !name.trim()}
            onClick={async () => {
              setBusy(true);
              try {
                onClose(await createApiKey(name, scopes));
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy && <Loader2 size={14} className="animate-spin" />} Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Shown once, immediately after minting.
 *
 * Only a hash is stored, so this really is the only time the value exists
 * anywhere outside the clipboard. The dialog says so plainly and does not
 * close on an outside click, because dismissing it by accident means reissuing.
 */
function MintedKeyDialog({
  apiKey,
  onClose,
}: {
  apiKey: ApiKeyRow;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <Dialog open onOpenChange={() => undefined}>
      <DialogContent onPointerDownOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>Copy this key now</DialogTitle>
          <DialogDescription>
            Only a hash of it is stored. Once you close this dialog there is no
            way to see it again — you would have to issue a new one.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="flex items-center gap-2 rounded-lg border border-[var(--sl-line)] bg-[var(--sl-soft)] p-3 bg-[var(--sl-card)]">
            <code className="min-w-0 flex-1 break-all font-mono text-xs">
              {apiKey.key}
            </code>
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                await navigator.clipboard.writeText(apiKey.key ?? "");
                setCopied(true);
              }}
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button onClick={onClose} disabled={!copied} variant={copied ? "default" : "secondary"}>
            {copied ? "Done" : "Copy it first"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
