"use client";

import { Loader2, ShieldAlert, UserPlus } from "lucide-react";
import { useState } from "react";

import { PageShell, QueryState } from "@/components/studio/PageShell";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
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
import { useAuth } from "@/lib/auth";
import {
  invitePerson,
  listPeople,
  removePerson,
  setPersonRole,
  type Membership,
} from "@/lib/studio-api";

/**
 * Per-site memberships.
 *
 * This is the *site* role, which is what governs the studio. It is separate
 * from the account-level role on the profile screen, and the difference is
 * load-bearing: someone can be an author on one site and an owner of another,
 * and collapsing the two would mean granting site access by changing a global
 * flag.
 */

const ROLES = [
  {
    value: "owner",
    label: "Owner",
    blurb: "Everything, including settings, API keys and this screen.",
  },
  {
    value: "editor",
    label: "Editor",
    blurb: "Publish and unpublish anything; manage categories, tags and redirects.",
  },
  {
    value: "author",
    label: "Author",
    blurb: "Write and submit their own drafts. Cannot publish.",
  },
  { value: "viewer", label: "Viewer", blurb: "Read-only access to the studio." },
] as const;

export default function PeoplePage() {
  const { user } = useAuth();
  const [inviting, setInviting] = useState(false);
  const { data, loading, error, refresh } = useStudioQuery(() => listPeople(), []);
  const rows = data?.results ?? [];
  const owners = rows.filter((row) => row.role === "owner").length;

  return (
    <PageShell
      title="People"
      description="Who can work on this site, and what they can do here."
      actions={
        <Button size="sm" onClick={() => setInviting(true)}>
          <UserPlus size={14} /> Add someone
        </Button>
      }
    >
      <QueryState
        loading={loading}
        error={error}
        isEmpty={rows.length === 0}
        empty="Nobody has been given access to this site yet."
      >
        <ul className="divide-y divide-[var(--sl-line)] rounded-xl border border-[var(--sl-line)] bg-[var(--sl-card)]">
          {rows.map((membership) => (
            <PersonRow
              key={membership.id}
              membership={membership}
              isSelf={membership.user.email === user?.email}
              isLastOwner={membership.role === "owner" && owners === 1}
              onChanged={refresh}
            />
          ))}
        </ul>
      </QueryState>

      {inviting && (
        <InviteDialog
          onClose={(changed) => {
            setInviting(false);
            if (changed) refresh();
          }}
        />
      )}
    </PageShell>
  );
}

function PersonRow({
  membership,
  isSelf,
  isLastOwner,
  onChanged,
}: {
  membership: Membership;
  isSelf: boolean;
  isLastOwner: boolean;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (err: unknown) {
      const response = (err as { response?: { data?: { detail?: string } } }).response;
      // The server refuses to strand a site without an owner; its sentence
      // explains what to do first, so show it rather than a generic failure.
      setError(response?.data?.detail ?? "That change was refused.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--sl-action)] text-xs font-semibold text-white">
        {(membership.user.name || membership.user.email).slice(0, 1).toUpperCase()}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-[var(--sl-ink)]">
          {membership.user.name || membership.user.email}
          {isSelf && <span className="ml-1.5 text-xs text-[var(--sl-muted)]">(you)</span>}
        </span>
        <span className="block truncate text-xs text-[var(--sl-muted)]">
          {membership.user.email}
        </span>
      </span>

      {isLastOwner && (
        <span
          className="flex items-center gap-1 text-xs text-amber-600"
          title="A site must always have at least one owner."
        >
          <ShieldAlert size={13} /> only owner
        </span>
      )}

      <select
        className="input-field h-9 w-32 py-0 text-sm"
        value={membership.role}
        disabled={busy}
        onChange={(e) => run(() => setPersonRole(membership.id, e.target.value))}
      >
        {ROLES.map((role) => (
          <option key={role.value} value={role.value}>
            {role.label}
          </option>
        ))}
      </select>

      <Button
        size="sm"
        variant="ghost"
        className="text-red-600"
        disabled={busy}
        onClick={() => run(() => removePerson(membership.id))}
      >
        {busy ? <Loader2 size={13} className="animate-spin" /> : "Remove"}
      </Button>

      {error && <p className="w-full text-xs text-red-600">{error}</p>}
    </li>
  );
}

function InviteDialog({ onClose }: { onClose: (changed: boolean) => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("author");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await invitePerson(email, role);
      onClose(true);
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, string[]> } }).response
        ?.data;
      setError(data ? Object.values(data).flat().join(" ") : "Could not add them.");
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={() => onClose(false)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add someone to this site</DialogTitle>
          <DialogDescription>
            They need an account already — this grants access, it does not create
            one.
          </DialogDescription>
        </DialogHeader>
        <DialogBody className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">Email</span>
            <input
              type="email"
              className="input-field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@example.com"
              autoFocus
            />
          </label>
          <fieldset>
            <legend className="mb-2 text-xs font-medium text-[var(--sl-muted)]">Role</legend>
            <div className="space-y-1">
              {ROLES.map((option) => (
                <label
                  key={option.value}
                  className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]"
                >
                  <input
                    type="radio"
                    name="role"
                    className="mt-1"
                    checked={role === option.value}
                    onChange={() => setRole(option.value)}
                  />
                  <span>
                    <span className="block font-medium text-[var(--sl-ink)]">
                      {option.label}
                    </span>
                    <span className="block text-xs text-[var(--sl-muted)]">{option.blurb}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onClose(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !email.includes("@")}>
            {busy && <Loader2 size={14} className="animate-spin" />} Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
