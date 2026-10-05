/**
 * Product and publication identity.
 *
 * Storyloom is the CMS (platform). Meridian is the demo tenant publication —
 * a journal that actually uses the product.
 */

export const PLATFORM = {
  name: "Storyloom",
  tagline: "A new dimension to every story.",
  description:
    "Storyloom is a bilingual publishing platform. Create interactive articles with annotations, image hotspots, and media chapters, then review and publish together in one editorial studio.",
  keywords: [
    "interactive articles",
    "bilingual CMS",
    "Bangla publishing",
    "editorial studio",
    "newsroom CMS",
    "annotations",
    "media chapters",
    "SEO",
  ],
  ogImage: "/og/storyloom.png",
  ogImageAlt: "Storyloom — a new dimension to every story",
} as const;

export const TENANT_PUBLICATION = {
  name: "Meridian",
  tagline: "A journal of systems, space, and statecraft.",
  description:
    "Meridian publishes long-form reporting and analysis at the intersection of astronomy, technology, geopolitics, and system design.",
  keywords: [
    "astronomy",
    "technology",
    "geopolitics",
    "system design",
    "long-form journalism",
    "Meridian journal",
  ],
  ogImage: "/og/tenant.jpg",
  ogImageAlt: "Meridian — a journal of systems, space, and statecraft",
  slug: "meridian",
} as const;
