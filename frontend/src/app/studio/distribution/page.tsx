"use client";

import { AlertTriangle, Copy, Check, Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { DeliveryList } from "@/components/studio/DeliveryList";
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
import {
  deleteDestination,
  enableDestination,
  listDeliveries,
  listDestinations,
  listSites,
  saveDestination,
  type Destination,
  type DeliveryState,
} from "@/lib/studio-api";

const STATE_FILTERS: Array<{ value: DeliveryState | ""; label: string }> = [
  { value: "", label: "All" },
  { value: "failed", label: "Retrying" },
  { value: "abandoned", label: "Gave up" },
  { value: "delivered", label: "Delivered" },
];

export default function DistributionPage() {
  return (
    <PageShell
      title="Distribution"
      description="Where published content is pushed, and what happened when it got there. Every request is HMAC-signed and carries an event id the receiver can dedupe on."
    >
      <Tabs defaultValue="destinations">
        <TabsList>
          <TabsTrigger value="destinations">Destinations</TabsTrigger>
          <TabsTrigger value="deliveries">Delivery log</TabsTrigger>
        </TabsList>
        <TabsContent value="destinations" className="mt-5">
          <Destinations />
        </TabsContent>
        <TabsContent value="deliveries" className="mt-5">
          <Deliveries />
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}

function Destinations() {
  const { data, loading, error, refresh } = useStudioQuery(listDestinations, []);
  const [editing, setEditing] = useState<Destination | "new" | null>(null);
  const [minted, setMinted] = useState<Destination | null>(null);
  const rows = data ?? [];

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button size="sm" onClick={() => setEditing("new")}>
          <Plus size={14} /> New destination
        </Button>
      </div>

      <QueryState
        loading={loading}
        error={error}
        isEmpty={rows.length === 0}
        empty="No destinations yet. Add one to push published articles to another site or a partner's API."
      >
        <ul className="divide-y divide-[var(--sl-line)] rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
          {rows.map((destination) => (
            <li key={destination.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-[var(--sl-ink)]">
                  {destination.name}
                </span>
                <span className="block truncate font-mono text-xs text-[var(--sl-muted)]">
                  {destination.kind === "site"
                    ? (destination.target_site_name ?? "—")
                    : destination.endpoint_url}
                </span>
              </span>

              <Badge tone="slate">{destination.kind.replace("_", " ")}</Badge>

              {destination.disabled_at ? (
                <span className="flex items-center gap-2">
                  <Badge tone="red">
                    <AlertTriangle size={11} /> disabled
                  </Badge>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      await enableDestination(destination.id);
                      refresh();
                    }}
                  >
                    Re-enable
                  </Button>
                </span>
              ) : destination.consecutive_failures > 0 ? (
                // Shown before the auto-disable fires, so a degrading endpoint
                // is visible while there is still time to fix it.
                <Badge tone="amber">
                  {destination.consecutive_failures} failures in a row
                </Badge>
              ) : (
                <Badge tone={destination.is_active ? "green" : "slate"}>
                  {destination.is_active ? "active" : "paused"}
                </Badge>
              )}

              <Button size="sm" variant="ghost" onClick={() => setEditing(destination)}>
                Edit
              </Button>
            </li>
          ))}
        </ul>
      </QueryState>

      {destinationDisabledNote(rows)}

      {editing && (
        <DestinationDialog
          destination={editing === "new" ? null : editing}
          onClose={(created) => {
            setEditing(null);
            if (created) {
              refresh();
              if (created.secret) setMinted(created);
            }
          }}
        />
      )}
      {minted && <SecretDialog destination={minted} onClose={() => setMinted(null)} />}
    </div>
  );
}

function destinationDisabledNote(rows: Destination[]) {
  const disabled = rows.filter((d) => d.disabled_at).length;
  if (!disabled) return null;
  return (
    <p className="mt-3 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
      <AlertTriangle size={15} className="mt-0.5 shrink-0" />
      {disabled} destination{disabled === 1 ? " was" : "s were"} switched off after
      repeated failures and {disabled === 1 ? "is" : "are"} no longer receiving
      anything. Fix the receiver, then re-enable — queued deliveries resume from
      the delivery log.
    </p>
  );
}

function Deliveries() {
  const [state, setState] = useState<DeliveryState | "">("");
  const { data, loading, error, refresh } = useStudioQuery(
    () => listDeliveries(state ? { state } : {}),
    [state],
  );
  const rows = data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1.5">
        {STATE_FILTERS.map((filter) => (
          <button
            key={filter.value || "all"}
            onClick={() => setState(filter.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              state === filter.value
                ? "bg-[var(--sl-card)] text-white bg-[var(--sl-action)] text-[var(--sl-ink)]"
                : "bg-[var(--sl-soft)] text-[var(--sl-ink)] hover:bg-[var(--sl-soft)] bg-[var(--sl-card)]"
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <QueryState
        loading={loading}
        error={error}
        isEmpty={rows.length === 0}
        empty={
          state
            ? "Nothing in this state."
            : "Nothing has been delivered yet. Publishing an article fans it out to every active destination."
        }
      >
        <DeliveryList deliveries={rows} onChanged={refresh} />
      </QueryState>
    </div>
  );
}

const KINDS = [
  { value: "site", label: "Owned site", hint: "Another tenant of this CMS." },
  { value: "webhook", label: "Webhook", hint: "Any URL that accepts a signed POST." },
  { value: "partner_api", label: "Partner API", hint: "A third party's endpoint." },
];

function DestinationDialog({
  destination,
  onClose,
}: {
  destination: Destination | null;
  onClose: (created: Destination | null) => void;
}) {
  const { data: sites } = useStudioQuery(listSites, []);
  const [name, setName] = useState(destination?.name ?? "");
  const [kind, setKind] = useState(destination?.kind ?? "webhook");
  const [targetSite, setTargetSite] = useState<number | null>(
    destination?.target_site ?? null,
  );
  const [url, setUrl] = useState(destination?.endpoint_url ?? "");
  const [isActive, setIsActive] = useState(destination?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const saved = await saveDestination(destination?.id ?? null, {
        name,
        kind: kind as Destination["kind"],
        target_site: kind === "site" ? targetSite : null,
        endpoint_url: kind === "site" ? "" : url,
        is_active: isActive,
      });
      onClose(saved);
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, string[]> } }).response
        ?.data;
      setError(
        data ? Object.values(data).flat().join(" ") : "Could not save this destination.",
      );
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={() => onClose(null)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {destination ? "Edit destination" : "New destination"}
          </DialogTitle>
          <DialogDescription>
            Published articles are POSTed here, signed with a shared secret.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">Name</span>
            <input
              className="input-field"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </label>

          <fieldset>
            <legend className="mb-2 text-xs font-medium text-[var(--sl-muted)]">Kind</legend>
            <div className="space-y-1">
              {KINDS.map((option) => (
                <label
                  key={option.value}
                  className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]"
                >
                  <input
                    type="radio"
                    name="kind"
                    className="mt-1"
                    checked={kind === option.value}
                    onChange={() => setKind(option.value as Destination["kind"])}
                  />
                  <span>
                    <span className="block font-medium text-[var(--sl-ink)]">
                      {option.label}
                    </span>
                    <span className="block text-xs text-[var(--sl-muted)]">{option.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          {kind === "site" ? (
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">
                Target site
              </span>
              <select
                className="input-field"
                value={targetSite ?? ""}
                onChange={(e) => setTargetSite(Number(e.target.value) || null)}
              >
                <option value="">Choose a site…</option>
                {(sites ?? []).map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-[var(--sl-muted)]">
                Its revalidation endpoint is used automatically.
              </span>
            </label>
          ) : (
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">
                Endpoint URL
              </span>
              <input
                className="input-field font-mono text-sm"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://partner.example.com/hooks/cms"
              />
            </label>
          )}

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
          {destination && (
            <Button
              variant="ghost"
              className="mr-auto text-red-600"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                await deleteDestination(destination.id);
                onClose({ ...destination });
              }}
            >
              <Trash2 size={14} /> Delete
            </Button>
          )}
          <Button variant="secondary" onClick={() => onClose(null)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !name.trim()}>
            {busy && <Loader2 size={14} className="animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The signing secret, shown once.
 *
 * Only the server keeps it after this; there is no endpoint that returns it
 * again. The receiver needs it to verify our signature, so a dismissed dialog
 * means recreating the destination.
 */
function SecretDialog({
  destination,
  onClose,
}: {
  destination: Destination;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <Dialog open onOpenChange={() => undefined}>
      <DialogContent onPointerDownOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>Copy the signing secret</DialogTitle>
          <DialogDescription>
            The receiver verifies our <code>X-CMS-Signature</code> header with
            this. It is not shown again — losing it means recreating the
            destination.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <div className="flex items-center gap-2 rounded-lg border border-[var(--sl-line)] bg-[var(--sl-soft)] p-3 bg-[var(--sl-card)]">
            <code className="min-w-0 flex-1 break-all font-mono text-xs">
              {destination.secret}
            </code>
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                await navigator.clipboard.writeText(destination.secret ?? "");
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
