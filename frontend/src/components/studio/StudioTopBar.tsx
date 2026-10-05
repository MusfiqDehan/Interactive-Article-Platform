"use client";

import { Check, ChevronDown, ExternalLink, LogOut, Globe } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";

import ThemeToggle from "@/components/layout/ThemeToggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";
import { listSites, type SiteOption } from "@/lib/studio-api";

/**
 * Top bar: site switcher, view-site link, theme, account.
 *
 * The site switcher is the piece that makes the studio multi-tenant in
 * practice. It writes the chosen slug to `localStorage`, which the studio Axios
 * client sends as `X-CMS-Site`; the backend validates that header against the
 * user's SiteMembership, so picking a site here can never grant access to one.
 */
/**
 * localStorage is an external store, so read it as one.
 *
 * `useState("")` + `useEffect(setCurrent(...))` would render the wrong site for
 * one frame and cost an extra render pass; `useSyncExternalStore` states the
 * server/client difference directly and hydrates without a mismatch.
 */
const subscribeToStorage = (onChange: () => void) => {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
};

export function StudioTopBar() {
  const { user, logout } = useAuth();
  const [sites, setSites] = useState<SiteOption[]>([]);
  const current = useSyncExternalStore(
    subscribeToStorage,
    () => localStorage.getItem("studio-site") || "",
    () => "",
  );

  useEffect(() => {
    // `/sites/` answers "which tenants may I open?", which is the one question
    // that cannot be asked from inside a single tenant -- so it is scoped by
    // membership rather than by the resolved site.
    listSites()
      .then(setSites)
      // A missing site list must not break the shell -- the studio still works
      // against the tenant resolved from the request host.
      .catch(() => setSites([]));
  }, []);

  const choose = (slug: string) => {
    if (slug) localStorage.setItem("studio-site", slug);
    else localStorage.removeItem("studio-site");
    // A full reload, not a router refresh: every cached response on the page
    // belongs to the previous tenant.
    window.location.reload();
  };

  const activeSite = sites.find((s) => s.slug === current) ?? sites[0];

  return (
    <header className="sl-admin-topbar">
      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium text-[var(--sl-ink)] transition hover:bg-[var(--sl-soft)] focus:outline-none focus:ring-2 focus:ring-ring hover:bg-[var(--sl-card)]">
          <Globe size={15} className="text-[var(--sl-muted)]" />
          {activeSite?.name ?? "Default site"}
          <ChevronDown size={14} className="text-[var(--sl-muted)]" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuLabel>Switch site</DropdownMenuLabel>
          {sites.length === 0 && (
            <DropdownMenuItem disabled>No sites available</DropdownMenuItem>
          )}
          {sites.map((site) => (
            <DropdownMenuItem key={site.id} onSelect={() => choose(site.slug)}>
              <Check
                size={14}
                className={site.slug === current ? "opacity-100" : "opacity-0"}
              />
              {site.name}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="flex items-center gap-1">
        {activeSite?.base_url && (
          <a
            href={activeSite.base_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm transition hover:bg-[var(--sl-soft)] hover:text-[var(--sl-ink)] hover:bg-[var(--sl-card)] hover:text-[var(--sl-muted)]"
          >
            View site <ExternalLink size={13} />
          </a>
        )}
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label="Account menu"
            className="sl-admin-avatar flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {(user?.first_name || user?.username || user?.email || "?")
              .slice(0, 1)
              .toUpperCase()}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/profile">Profile</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => logout()}>
              <LogOut size={14} /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
