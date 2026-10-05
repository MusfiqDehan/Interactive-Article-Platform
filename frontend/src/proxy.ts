import { NextResponse, type NextRequest } from "next/server";

import type { RedirectRule } from "@/lib/public-types";

/**
 * Edge redirect handling.
 *
 * Named `proxy` rather than `middleware`: Next 16 renamed the convention, and
 * the old filename still builds but logs a deprecation on every build.
 *
 * The whole active redirect set is fetched once and held in module scope with a
 * short TTL. Querying the database per navigation would tax every page view to
 * serve a rule that applies to almost none of them.
 *
 * Regex rules are capped: a runaway pattern set would turn every request into a
 * linear scan at the edge.
 */

const CACHE_TTL_MS = 5 * 60 * 1000;
const MAX_REGEX_RULES = 200;

let cache: { rules: RedirectRule[]; fetchedAt: number } | null = null;
let inflight: Promise<RedirectRule[]> | null = null;

async function loadRules(): Promise<RedirectRule[]> {
  const now = Date.now();
  if (cache && now - cache.fetchedAt < CACHE_TTL_MS) return cache.rules;
  // Collapse concurrent refreshes into one request.
  if (inflight) return inflight;

  const apiUrl = (
    process.env.CMS_INTERNAL_API_URL ||
    `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://backend:8003/api"}/v1`
  ).replace(/\/$/, "");
  const apiKey = process.env.CMS_SITE_API_KEY || "";

  inflight = fetch(`${apiUrl}/public/redirects/`, {
    headers: { "X-API-Key": apiKey, Accept: "application/json" },
    cache: "no-store",
  })
    .then((res) => (res.ok ? (res.json() as Promise<RedirectRule[]>) : []))
    .catch(() => [])
    .then((rules) => {
      cache = { rules, fetchedAt: Date.now() };
      inflight = null;
      return rules;
    });

  return inflight;
}

function normalise(path: string): string {
  if (!path || path === "/") return "/";
  return path.endsWith("/") ? path.slice(0, -1) : path;
}

export default async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // Never redirect internal or asset traffic.
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const rules = await loadRules();
  if (rules.length === 0) return NextResponse.next();

  const path = normalise(pathname);

  const exact = rules.find((rule) => !rule.is_regex && rule.source_path === path);
  if (exact) {
    return NextResponse.redirect(
      buildTarget(request, exact.target_path, search),
      exact.status_code,
    );
  }

  let checked = 0;
  for (const rule of rules) {
    if (!rule.is_regex) continue;
    if (++checked > MAX_REGEX_RULES) break;
    try {
      const pattern = new RegExp(rule.source_path);
      if (pattern.test(path)) {
        const target = path.replace(pattern, rule.target_path);
        return NextResponse.redirect(
          buildTarget(request, target, search),
          rule.status_code,
        );
      }
    } catch {
      // A malformed pattern must not break every request.
    }
  }

  return NextResponse.next();
}

function buildTarget(request: NextRequest, target: string, search: string): URL {
  if (target.startsWith("http://") || target.startsWith("https://")) {
    return new URL(target);
  }
  const url = new URL(target, request.url);
  // Preserve query parameters (utm tags, etc.) across the redirect.
  if (search && !target.includes("?")) url.search = search;
  return url;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
