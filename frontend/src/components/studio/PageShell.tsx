"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

/** Header + body chrome shared by every studio screen. */
export function PageShell({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="sl-admin-page">
      <div className="sl-admin-page-heading">
        <div>
          <span className="sl-eyebrow">YOUR EDITORIAL WORKSPACE</span>
          <h1>{title}</h1>
          {description && <p className="sl-admin-description">{description}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}

/**
 * The three states every fetched screen has.
 *
 * `empty` is a required prop rather than an optional nicety: an empty list
 * rendered as blank space is indistinguishable from a screen that failed
 * quietly, and that ambiguity is what sends people to reload the page.
 */
export function QueryState({
  loading,
  error,
  isEmpty,
  empty,
  children,
}: {
  loading: boolean;
  error: string | null;
  isEmpty: boolean;
  empty: ReactNode;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div role="status" className="sl-admin-query">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    );
  }
  if (error) {
    return (
      <div
        role="alert"
        className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
      >
        <AlertCircle size={16} className="mt-0.5 shrink-0" />
        {error}
      </div>
    );
  }
  if (isEmpty) {
    return <div className="sl-admin-query sl-admin-query-empty">{empty}</div>;
  }
  return <>{children}</>;
}
