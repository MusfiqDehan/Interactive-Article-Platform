/**
 * Counting characters the way a platform does.
 *
 * A mirror of `apps/social/constraints.py`. The two must agree, which is why
 * the *limits* come from the API rather than being duplicated here — this file
 * holds only the counting algorithm, and there is a server-side test asserting
 * the same inputs produce the same numbers.
 *
 * Two rules, both of which a naive `text.length` gets wrong:
 *
 * 1. **X counts every URL as 23 characters**, however long it really is.
 * 2. **Length is in grapheme clusters.** `"👨‍👩‍👧".length` is 8 and a reader sees
 *    one character. For Bengali the gap is routine: `"ক্ষ"` is three code units
 *    and one letter, so a code-unit counter tells an author their post is a
 *    third longer than it looks and refuses text that would have fit.
 */

const URL_RE = /https?:\/\/\S+/g;

/** Brahmic viramas — each binds the consonant that follows into a conjunct. */
const VIRAMAS = new Set([
  "्", "্", "੍", "્", "୍", "்",
  "్", "್", "്", "්", "ฺ", "྄",
]);
const ZWJ = "‍";

/**
 * Prefer the platform's own segmenter when it exists — it implements the full
 * UAX #29 algorithm, which this file only approximates.
 */
const segmenter =
  typeof Intl !== "undefined" && "Segmenter" in Intl
    ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
    : null;

export function graphemes(text: string): string[] {
  if (!text) return [];
  if (segmenter) {
    return Array.from(segmenter.segment(text), (entry) => entry.segment);
  }

  const clusters: string[] = [];
  let attachNext = false;
  for (const char of text) {
    const code = char.codePointAt(0) ?? 0;
    const attaches =
      attachNext ||
      /\p{Mn}|\p{Mc}|\p{Me}/u.test(char) ||
      (code >= 0xfe00 && code <= 0xfe0f) ||
      (code >= 0x1f3fb && code <= 0x1f3ff);
    attachNext = char === ZWJ || VIRAMAS.has(char);

    if ((attaches || char === ZWJ) && clusters.length) {
      clusters[clusters.length - 1] += char;
    } else {
      clusters.push(char);
    }
  }
  return clusters;
}

export function graphemeLength(text: string): number {
  return graphemes(text).length;
}

/** Caption length as `urlLength` (from the platform spec) implies. */
export function countedLength(text: string, urlLength: number | null): number {
  if (urlLength === null) return graphemeLength(text);

  let total = 0;
  let cursor = 0;
  URL_RE.lastIndex = 0;
  for (const match of text.matchAll(URL_RE)) {
    const start = match.index ?? 0;
    total += graphemeLength(text.slice(cursor, start));
    total += urlLength;
    cursor = start + match[0].length;
  }
  return total + graphemeLength(text.slice(cursor));
}

/** Cut to `limit` clusters on a word boundary — used by the preview cards. */
export function truncateGraphemes(text: string, limit: number): string {
  const clusters = graphemes(text);
  if (limit <= 0) return "";
  if (clusters.length <= limit) return text;
  const cut = clusters.slice(0, limit).join("");
  const space = cut.lastIndexOf(" ");
  return space > cut.length * 0.6 ? cut.slice(0, space) : cut;
}
