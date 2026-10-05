"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Menu, X } from "lucide-react";
import ThemeToggle from "./ThemeToggle";
import { useAuth } from "@/lib/auth";
import { StoryloomWordmark } from "@/components/brand/StoryloomMark";

export default function Header() {
  const [open, setOpen] = useState(false);
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const links = [
    { href: "/home", label: "Journal" },
    { href: "/articles", label: "Articles" },
    { href: "/categories", label: "Categories" },
  ];
  const workspace = user?.role === "reader" ? "/dashboard" : "/studio";
  const active = (href: string) =>
    pathname === href || pathname.startsWith(`${href}/`);
  const accountLinks = isAuthenticated ? (
    <>
      <Link
        href={workspace}
        className="sl-button sl-button-small"
        onClick={() => setOpen(false)}
      >
        {workspace === "/studio" ? "Open studio" : "Dashboard"}
        <ArrowRight size={15} />
      </Link>
      <button
        className="sl-nav-link"
        onClick={() => {
          logout();
          setOpen(false);
        }}
      >
        Sign out
      </button>
    </>
  ) : (
    <>
      <Link
        href="/login"
        className="sl-nav-link"
        aria-current={pathname === "/login" ? "page" : undefined}
        onClick={() => setOpen(false)}
      >
        Sign in
      </Link>
      <Link
        href="/register"
        className="sl-button sl-button-small"
        onClick={() => setOpen(false)}
      >
        Get started
        <ArrowRight size={15} />
      </Link>
    </>
  );
  return (
    <header className="sl-header">
      <div className="sl-container sl-header-row">
        <Link href="/" className="sl-brand" aria-label="Storyloom home">
          <StoryloomWordmark markSize={36} />
        </Link>
        <nav className="sl-desktop-links" aria-label="Main navigation">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="sl-nav-link"
              aria-current={active(link.href) ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="sl-header-actions">
          <ThemeToggle />
          <div className="sl-desktop-links">{accountLinks}</div>
          <button
            className="sl-mobile-toggle"
            aria-label="Toggle navigation"
            aria-expanded={open}
            aria-controls="sl-mobile-navigation"
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>
      {open && (
        <nav
          id="sl-mobile-navigation"
          className="sl-mobile-links"
          aria-label="Mobile navigation"
        >
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active(link.href) ? "page" : undefined}
              onClick={() => setOpen(false)}
            >
              {link.label}
            </Link>
          ))}
          {accountLinks}
        </nav>
      )}
    </header>
  );
}
