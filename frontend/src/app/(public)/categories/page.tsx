import type { Metadata } from "next";
import { PageIntro, DiscoveryBanner } from "@/components/storyloom/Primitives";
import { CategoryExplorer } from "@/components/storyloom/CategoryExplorer";

import { getCategoriesSafe, getSiteSafe } from "@/lib/api.server";
import { absoluteUrl, socialMetadata } from "@/lib/seo";

export const revalidate = 3600;

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteSafe();
  const title = "Categories";
  const description = `Browse ${site.site_title || site.name} articles by topic.`;
  const url = absoluteUrl("/categories", site.base_url);
  const image = site.default_og_image || "/og/platform.jpg";
  return {
    title,
    description,
    alternates: { canonical: url },
    ...socialMetadata({
      title: `${title} | ${site.site_title || site.name}`,
      description,
      url,
      image,
      imageAlt: description,
      locale: site.locale,
      siteName: site.name,
    }),
  };
}

export default async function CategoriesPage() {
  const categories = await getCategoriesSafe();

  return (
    <div className="sl-container sl-listing">
      <PageIntro
        eyebrow="FOLLOW A THREAD"
        title="A world of ideas."
        accent="Find yours."
        description="Every interest is a starting point. Explore topics that make you think, wonder, and look a little closer."
      >
        <span className="sl-intro-note">
          Different perspectives.
          <br />
          Endless possibilities.
        </span>
      </PageIntro>
      <CategoryExplorer categories={categories} />
      <DiscoveryBanner />
    </div>
  );
}
