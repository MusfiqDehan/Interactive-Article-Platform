import type { Metadata } from "next";
import Link from "next/link";

import { ArticleCard } from "@/components/article/ArticleCard";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { EmptyState, DiscoveryBanner } from "@/components/storyloom/Primitives";
import { JsonLd } from "@/components/seo/JsonLd";
import { getCategoriesSafe, getFeaturedArticles, getSiteSafe, listArticles } from "@/lib/api.server";
import { TENANT_PUBLICATION } from "@/lib/brand";
import { organizationSchema, websiteSchema } from "@/lib/schema";
import { absoluteUrl, socialMetadata } from "@/lib/seo";

export const revalidate = 300;

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteSafe();
  const base = site.base_url;
  const title = `${TENANT_PUBLICATION.name} — ${TENANT_PUBLICATION.tagline.replace(/\.$/, "")}`;
  const description = TENANT_PUBLICATION.description;
  const url = absoluteUrl("/home", base);

  return {
    title: { absolute: title },
    description,
    keywords: [...TENANT_PUBLICATION.keywords],
    alternates: { canonical: url },
    ...socialMetadata({
      title,
      description,
      url,
      image: TENANT_PUBLICATION.ogImage,
      imageAlt: TENANT_PUBLICATION.ogImageAlt,
      locale: site.locale,
      siteName: TENANT_PUBLICATION.name,
    }),
  };
}

export default async function TenantHomePage() {
  const [site, featured, latest, categories] = await Promise.all([
    getSiteSafe(),
    getFeaturedArticles().catch(() => []),
    listArticles({ page_size: 9 }).catch(() => null),
    getCategoriesSafe(),
  ]);

  const stories = [...featured, ...(latest?.results ?? [])].filter(
    (article, index, all) => all.findIndex((item) => item.id === article.id) === index,
  );
  const hero = stories[0];
  const rest = stories.slice(1, 7);

  return (
    <>
      <JsonLd
        data={[
          {
            ...organizationSchema(site),
            name: TENANT_PUBLICATION.name,
            description: TENANT_PUBLICATION.description,
            logo: absoluteUrl(TENANT_PUBLICATION.ogImage, site.base_url),
          },
          {
            ...websiteSchema(site),
            name: TENANT_PUBLICATION.name,
            url: absoluteUrl("/home", site.base_url),
          },
        ]}
      />

      <div className="sl-container sl-journal">
        <header className="sl-journal-masthead">
          <div className="sl-journal-edition"><span className="sl-eyebrow">INDEPENDENT IDEAS. CONNECTED PERSPECTIVES.</span><span>A Storyloom journal</span></div>
          <h1>{TENANT_PUBLICATION.name}<span aria-hidden="true">.</span></h1>
          <div className="sl-journal-deck"><p>{TENANT_PUBLICATION.tagline}</p><Link href="/articles">Explore the archive <ArrowUpRight size={17} /></Link></div>
        </header>
        <nav className="sl-journal-topics" aria-label="Journal topics">
          <span className="sl-eyebrow">THE DESKS</span>
          {categories.map((category) => <Link key={category.id} href={`/categories/${encodeURIComponent(category.slug)}`}>{category.name}<ArrowUpRight size={14} /></Link>)}
          <Link href="/categories">All topics <ArrowRight size={14} /></Link>
        </nav>
        {hero ? (
          <section className="sl-journal-lead" aria-label="Featured reading">
            <div><div className="sl-journal-section-title"><span className="sl-eyebrow">IN FOCUS</span><span>The lead story</span></div><ArticleCard article={hero} priority /></div>
            <aside className="sl-journal-notebook">
              <span className="sl-eyebrow">THE READING ROOM</span>
              <h2>A little further.<br /><em>A little deeper.</em></h2>
              <p>Fresh perspectives on the systems that shape our world, and the universe beyond it.</p>
              <div className="sl-journal-reading-list">
                {rest.slice(0, 3).map((article, index) => (
                  <Link key={article.id} href={`/articles/${encodeURIComponent(article.slug)}`}><span className="sl-journal-number">0{index + 1}</span><div><span className="sl-eyebrow">{article.category?.name || "JOURNAL"} · {article.reading_time} MIN</span><h3>{article.title}</h3></div><ArrowUpRight size={17} /></Link>
                ))}
              </div>
              <Link className="sl-journal-text-link" href="/articles">Find your next read <ArrowRight size={17} /></Link>
            </aside>
          </section>
        ) : <EmptyState title={latest ? "The next story starts here." : "The journal is taking a moment."} description={latest ? "New perspectives are on their way. Explore our topics while you wait." : "We couldn’t load the stories. Please try again in a moment."} href={latest ? "/categories" : "/home"} action={latest ? "Explore topics" : "Try again"} />}
        {rest.length > 0 && (
          <section className="sl-journal-stories" aria-labelledby="journal-stories-title">
            <div className="sl-journal-section-heading"><div><span className="sl-eyebrow">WORTH YOUR ATTENTION</span><h2 id="journal-stories-title">From the desks<span>.</span></h2></div><Link href="/articles">All stories <ArrowRight size={17} /></Link></div>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">{rest.map((article) => <ArticleCard key={article.id} article={article} />)}</div>
          </section>
        )}
        <DiscoveryBanner />
      </div>
    </>
  );
}
