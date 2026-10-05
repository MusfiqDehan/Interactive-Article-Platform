"use client";

import { useState, useSyncExternalStore, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  type LucideIcon,
} from "lucide-react";
import { StoryloomMark } from "@/components/brand/StoryloomMark";
import { PLATFORM } from "@/lib/brand";

export type AdminNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  group: string;
  exact?: boolean;
};
const subscribe = (notify: () => void) => {
  window.addEventListener("storage", notify);
  window.addEventListener("studio-sidebar", notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener("studio-sidebar", notify);
  };
};
const subscribeMobile = (notify: () => void) => {
  const media = window.matchMedia("(max-width: 760px)");
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};
const readExpanded = () => {
  try {
    return localStorage.getItem("studio-sidebar-expanded") !== "0";
  } catch {
    return true;
  }
};

export function AdminShell({
  items,
  toolbar,
  children,
  label = "Editorial studio",
}: {
  items: AdminNavItem[];
  toolbar: ReactNode;
  children: ReactNode;
  label?: string;
}) {
  const pathname = usePathname();
  const mobile = useSyncExternalStore(
    subscribeMobile,
    () => window.matchMedia("(max-width: 760px)").matches,
    () => false,
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const expanded = useSyncExternalStore(subscribe, readExpanded, () => true);
  const toggle = () => {
    try {
      localStorage.setItem("studio-sidebar-expanded", expanded ? "0" : "1");
    } catch {
      /* Storage can be disabled by the browser. */
    }
    window.dispatchEvent(new Event("studio-sidebar"));
  };
  const groups = [...new Set(items.map((item) => item.group))];
  return (
    <div className={`sl-shell sl-admin ${expanded ? "" : "sl-admin-compact"}`}>
      <a className="sl-admin-skip" href="#workspace-content">
        Skip to workspace
      </a>
      <aside
        className={`sl-admin-sidebar ${mobileOpen ? "is-open" : ""}`}
        id="workspace-navigation"
        inert={mobile && !mobileOpen}
        onKeyDown={(event) => {
          if (event.key === "Escape") setMobileOpen(false);
        }}
      >
        <div className="sl-admin-brand">
          <Link href="/" aria-label="Storyloom home">
            <StoryloomMark size={37} title="" />
            <span>
              {PLATFORM.name}
              <small>{label}</small>
            </span>
          </Link>
          <button
            className="sl-admin-close"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <nav aria-label="Workspace sections">
          {groups.map((group) => (
            <div className="sl-admin-nav-group" key={group}>
              <p>{group}</p>
              {items
                .filter((item) => item.group === group)
                .map(({ href, label: text, icon: Icon, exact }) => {
                  const active = exact
                    ? pathname === href
                    : pathname === href || pathname.startsWith(`${href}/`);
                  return (
                    <Link
                      key={href}
                      href={href}
                      title={text}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setMobileOpen(false)}
                    >
                      <Icon size={18} />
                      <span>{text}</span>
                      {active && <i />}
                    </Link>
                  );
                })}
            </div>
          ))}
        </nav>
        <div className="sl-admin-sidebar-footer">
          <Link href="/articles" title="Explore the journal">
            <ArrowUpRight size={17} />
            <span>Explore the journal</span>
          </Link>
          <button
            className="sl-admin-collapse"
            onClick={toggle}
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
          >
            {expanded ? <ChevronLeft size={17} /> : <ChevronRight size={17} />}
            <span>Collapse sidebar</span>
          </button>
        </div>
      </aside>
      <div className="sl-admin-workspace">
        <div className="sl-admin-mobile-bar">
          <button
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
            aria-controls="workspace-navigation"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            <Menu size={20} />
          </button>
          <span>{label}</span>
          <StoryloomMark size={26} title="" />
        </div>
        {toolbar}
        <main id="workspace-content" className="sl-admin-content">
          {children}
        </main>
        <footer className="sl-admin-footnote">
          {PLATFORM.name}
          <span>A little structure. A lot of possibility.</span>
        </footer>
      </div>
    </div>
  );
}
