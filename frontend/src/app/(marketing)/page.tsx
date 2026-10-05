import type { Metadata } from "next";

import LandingPage from "@/components/landing";
import { JsonLd } from "@/components/seo/JsonLd";
import { getSiteSafe } from "@/lib/api.server";
import { PLATFORM } from "@/lib/brand";
import { publicEnv } from "@/lib/env.server";
import { organizationSchema, websiteSchema } from "@/lib/schema";
import { absoluteUrl, socialMetadata } from "@/lib/seo";

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteSafe();
  const base = site.base_url || publicEnv.siteUrl;
  const title = `${PLATFORM.name} — ${PLATFORM.tagline.replace(/\.$/, "")}`;
  const description = PLATFORM.description;
  const url = absoluteUrl("/", base);

  return {
    title: { absolute: title },
    description,
    keywords: [...PLATFORM.keywords],
    alternates: { canonical: url },
    ...socialMetadata({
      title,
      description,
      url,
      image: PLATFORM.ogImage,
      imageAlt: PLATFORM.ogImageAlt,
      locale: site.locale,
      siteName: PLATFORM.name,
    }),
  };
}

export default async function HomePage() {
  const site = await getSiteSafe();
  return (
    <>
      <JsonLd
        data={[
          organizationSchema(site),
          websiteSchema(site),
          {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            name: PLATFORM.name,
            applicationCategory: "BusinessApplication",
            operatingSystem: "Web",
            url: site.base_url,
            description: PLATFORM.description,
            offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
          },
        ]}
      />
      <LandingPage />
    </>
  );
}
