import type { Metadata } from "next";

import { PLATFORM } from "./brand";
import { publicEnv } from "./env.server";
import type { SiteConfig } from "./public-types";

/** Absolute URL for a path on this site. */
export function absoluteUrl(path: string, base?: string): string {
  const origin = (base || publicEnv.siteUrl).replace(/\/$/, "");
  if (!path || path === "/") return origin;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${origin}${path.startsWith("/") ? path : `/${path}`}`;
}

export function ogImage(path: string, alt: string, base?: string) {
  return {
    url: absoluteUrl(path, base),
    width: 1200,
    height: 630,
    alt,
  };
}

export function siteTitle(site: SiteConfig): string {
  return site.site_title || site.name || PLATFORM.name;
}

/**
 * Shared Open Graph + Twitter card fields for a public page.
 *
 * Images must be absolute: `metadataBase` covers relatives, but a missing
 * base (build-time fallback) would silently drop every card.
 */
export function socialMetadata({
  title,
  description,
  url,
  image,
  imageAlt,
  locale = "en",
  siteName = PLATFORM.name,
  type = "website",
}: {
  title: string;
  description: string;
  url: string;
  image: string;
  imageAlt: string;
  locale?: string;
  siteName?: string;
  type?: "website" | "article";
}): Pick<Metadata, "openGraph" | "twitter"> {
  const images = [ogImage(image, imageAlt)];
  return {
    openGraph: {
      type,
      url,
      title,
      description,
      siteName,
      locale: locale.replace("-", "_"),
      images,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [images[0].url],
    },
  };
}
