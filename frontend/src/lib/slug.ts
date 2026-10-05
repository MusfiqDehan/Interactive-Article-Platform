/**
 * One place to normalise a route slug.
 *
 * Slugs allow Unicode, so Bengali titles arrive percent-encoded. Getting the
 * decode/encode boundary wrong produces a 404 that only ever appears for
 * non-ASCII content -- the git history already contains three separate
 * "fix: decode article slug" commits.
 *
 * The contract, applied everywhere:
 *   route params / user input  -> normalizeSlug() -> always DECODED
 *   outbound HTTP requests     -> encodeURIComponent() at the call site
 *   generateStaticParams       -> returns DECODED (Next encodes when building)
 */

export function normalizeSlug(raw: string): string {
  if (!raw) return "";
  try {
    const decoded = decodeURIComponent(raw);
    // decodeURIComponent is not idempotent for strings containing a literal
    // "%", but re-decoding an already-decoded slug is the common case here and
    // must not corrupt it -- so decode once and stop.
    return decoded;
  } catch {
    // Malformed percent-encoding: use the raw value rather than throwing and
    // turning a bad URL into a 500.
    return raw;
  }
}

/** Decoded slug for display; encoded form for building an href. */
export function slugToHref(prefix: string, slug: string): string {
  return `${prefix}/${encodeURIComponent(normalizeSlug(slug))}`;
}
