import { createHmac, timingSafeEqual } from "node:crypto";

import { revalidatePath, revalidateTag } from "next/cache";
import { NextResponse, type NextRequest } from "next/server";

/**
 * On-demand revalidation, called by the CMS after a publish.
 *
 * Without this a publish would wait out the ISR window (up to an hour on
 * article pages). With it, the change is live in seconds and still fully
 * cached in between.
 *
 * Authentication is an HMAC over `{timestamp}.{body}` with a shared secret --
 * the same scheme the backend uses for outbound webhooks, so there is one
 * signing implementation and one thing to get right. The timestamp bounds
 * replay: a captured request is useless after five minutes.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TOLERANCE_SECONDS = 300;

function verify(secret: string, signature: string, timestamp: string, body: string) {
  const expected = createHmac("sha256", secret)
    .update(`${timestamp}.${body}`)
    .digest("hex");
  const provided = signature.replace(/^v1=/, "");

  // Length check first: timingSafeEqual throws on a length mismatch, and that
  // throw would itself be an oracle.
  if (provided.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(provided), Buffer.from(expected));
}

export async function POST(request: NextRequest) {
  const secret = process.env.CMS_REVALIDATE_SECRET;
  if (!secret) {
    return NextResponse.json(
      { error: "Revalidation is not configured." },
      { status: 503 },
    );
  }

  const signature = request.headers.get("X-CMS-Signature") || "";
  const timestamp = request.headers.get("X-CMS-Timestamp") || "";
  if (!signature || !timestamp) {
    return NextResponse.json({ error: "Missing signature." }, { status: 401 });
  }

  const skew = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!Number.isFinite(skew) || skew > TOLERANCE_SECONDS) {
    return NextResponse.json({ error: "Stale signature." }, { status: 401 });
  }

  const body = await request.text();
  if (!verify(secret, signature, timestamp, body)) {
    return NextResponse.json({ error: "Invalid signature." }, { status: 401 });
  }

  let payload: RevalidatePayload;
  try {
    payload = JSON.parse(body || "{}");
  } catch {
    return NextResponse.json({ error: "Malformed JSON." }, { status: 400 });
  }

  const { paths, tags } = resolveTargets(payload);
  const revalidated: { paths: string[]; tags: string[] } = { paths: [], tags: [] };

  for (const tag of tags) {
    // Next 16 made the second argument required: it says how long a stale entry
    // may still be served after the purge. `expire: 0` means "not at all",
    // which is the whole point of a publish webhook -- the alternative is
    // waiting out an ISR window we called this endpoint specifically to skip.
    // (`updateTag`, the other immediate option, is Server-Actions-only.)
    revalidateTag(tag, { expire: 0 });
    revalidated.tags.push(tag);
  }
  for (const path of paths) {
    revalidatePath(path);
    revalidated.paths.push(path);
  }

  return NextResponse.json({
    revalidated,
    // Echoed back so the CMS's delivery log records which event this response
    // was for; without it a retry and its original are indistinguishable in
    // the stored response snapshot.
    event_id: request.headers.get("X-CMS-Event-Id") ?? null,
    now: Date.now(),
  });
}

interface RevalidatePayload {
  /** Explicit form, sent by the publish chain. */
  paths?: string[];
  tags?: string[];
  /** Syndication form, sent to a `site` destination. */
  event?: string;
  article?: { slug?: string; path_slug?: string };
}

/**
 * Two callers, one endpoint.
 *
 * The publish chain sends the paths and tags it wants purged. A syndication
 * delivery sends the article itself, because a partner receiver has no idea
 * what our route structure looks like — so when the payload is an article, the
 * paths are derived here, where that knowledge actually lives.
 */
function resolveTargets(payload: RevalidatePayload) {
  if (payload.paths || payload.tags) {
    return { paths: payload.paths ?? [], tags: payload.tags ?? [] };
  }

  const slug = payload.article?.path_slug || payload.article?.slug;
  if (!slug) return { paths: [], tags: [] };

  return {
    // The article's own page plus every listing it can appear in. Purging only
    // the article leaves a stale card on the home page, which is the copy most
    // readers actually see.
    paths: ["/", "/articles", `/articles/${slug}`],
    tags: ["articles", `article:${slug}`, "sitemap"],
  };
}
