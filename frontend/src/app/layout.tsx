import type { Metadata } from "next";
import { Hind_Siliguri } from "next/font/google";

import { getSiteSafe } from "@/lib/api.server";
import { PLATFORM } from "@/lib/brand";
import { publicEnv } from "@/lib/env.server";
import { RuntimeConfigProvider } from "@/lib/runtime-config";
import { absoluteUrl, ogImage, siteTitle } from "@/lib/seo";

import "./globals.css";
import "@/components/storyloom/styles.css";
import { Providers } from "./providers";

const hindSiliguri = Hind_Siliguri({
  subsets: ["bengali", "latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-hind-siliguri",
});

/**
 * Root metadata, resolved per request from the tenant's SiteSettings.
 *
 * `metadataBase` is mandatory rather than nice-to-have: without it Next drops
 * every relative Open Graph image silently, so shared links render bare.
 */
export async function generateMetadata(): Promise<Metadata> {
  const origin = publicEnv.siteUrl || "http://localhost:3003";
  const fallbackImage = ogImage(PLATFORM.ogImage, PLATFORM.ogImageAlt, origin);
  const fallback: Metadata = {
    metadataBase: new URL(origin),
    title: {
      default: PLATFORM.name,
      template: `%s | ${PLATFORM.name}`,
    },
    description: PLATFORM.description,
    keywords: [...PLATFORM.keywords],
    applicationName: PLATFORM.name,
    authors: [{ name: PLATFORM.name }],
    creator: PLATFORM.name,
    publisher: PLATFORM.name,
    icons: {
      icon: [{ url: "/logo.svg", type: "image/svg+xml" }],
      apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
    },
    openGraph: {
      type: "website",
      siteName: PLATFORM.name,
      title: PLATFORM.name,
      description: PLATFORM.description,
      locale: "en_US",
      images: [fallbackImage],
    },
    twitter: {
      card: "summary_large_image",
      title: PLATFORM.name,
      description: PLATFORM.description,
      images: [fallbackImage.url],
    },
    robots: { index: true, follow: true },
  };

  try {
    const site = await getSiteSafe();
    const base = site.base_url || origin;
    const title = siteTitle(site);
    const description = site.default_meta_description || PLATFORM.description;
    const image = site.default_og_image
      ? ogImage(site.default_og_image, title, base)
      : ogImage(PLATFORM.ogImage, PLATFORM.ogImageAlt, base);

    return {
      metadataBase: new URL(base),
      title: {
        default: title,
        template: site.title_template?.includes("%s")
          ? site.title_template
          : `%s | ${title}`,
      },
      description,
      keywords: [...PLATFORM.keywords],
      applicationName: title,
      authors: [{ name: title, url: base }],
      creator: title,
      publisher: title,
      alternates: {
        canonical: base,
        types: { "text/plain": absoluteUrl("/llms.txt", base) },
      },
      icons: {
        icon: [{ url: "/logo.svg", type: "image/svg+xml" }],
        apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
      },
      openGraph: {
        type: "website",
        url: base,
        siteName: site.name || title,
        locale: (site.locale || "en").replace("-", "_"),
        title,
        description,
        images: [image],
      },
      twitter: {
        card: "summary_large_image",
        title,
        description,
        images: [image.url],
      },
      robots: {
        index: true,
        follow: true,
        googleBot: { index: true, follow: true, "max-image-preview": "large" },
      },
      verification: site.google_site_verification
        ? { google: site.google_site_verification }
        : undefined,
    };
  } catch {
    return fallback;
  }
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let locale = publicEnv.siteSlug ? "en" : "en";
  try {
    locale = (await getSiteSafe()).locale || "en";
  } catch {
    /* keep the default */
  }

  return (
    // lang is resolved from the tenant rather than hardcoded -- this platform
    // serves Bengali content and was declaring every page as English.
    //
    // The data-* attributes carry runtime config to non-React code (the studio
    // Axios client), which cannot read context. They are stamped here, on the
    // server, so the values exist before any script runs.
    <html
      lang={locale}
      data-api-base={publicEnv.apiBase}
      data-site-url={publicEnv.siteUrl}
      data-site-slug={publicEnv.siteSlug}
      data-events-key={publicEnv.eventsApiKey}
      suppressHydrationWarning
    >
      <body className={`${hindSiliguri.variable} font-sans`}>
        {/* Serializes runtime config into the RSC payload at request time, so
            one built image can serve any domain. */}
        <RuntimeConfigProvider value={publicEnv}>
          <Providers>{children}</Providers>
        </RuntimeConfigProvider>
      </body>
    </html>
  );
}
