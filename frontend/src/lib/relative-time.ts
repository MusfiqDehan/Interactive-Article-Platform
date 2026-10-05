/**
 * "3 days ago" without a date library.
 *
 * `Intl.RelativeTimeFormat` is in every browser this app supports and is
 * locale-aware for free, which matters for a bilingual publication — a
 * hand-rolled English string would have to be translated, and date-fns would
 * add a dependency and a locale bundle to say the same thing.
 */

const UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ["year", 31_536_000_000],
  ["month", 2_592_000_000],
  ["week", 604_800_000],
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
  ["second", 1000],
];

export function relativeTime(value: string | null | undefined, locale = "en"): string {
  if (!value) return "";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "";

  const delta = then - Date.now();
  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  for (const [unit, ms] of UNITS) {
    if (Math.abs(delta) >= ms || unit === "second") {
      return formatter.format(Math.round(delta / ms), unit);
    }
  }
  return "";
}
