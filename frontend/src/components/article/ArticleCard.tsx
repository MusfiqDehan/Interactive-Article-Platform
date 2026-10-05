import Link from "next/link";
import { ArrowUpRight, BookOpen } from "lucide-react";
import { normalizeMediaUrl } from "@/lib/media";
import type { PublicArticleListItem } from "@/lib/public-types";

/** Shared by article, search, and category listings. */
export function ArticleCard({
  article,
  priority = false,
}: {
  article: PublicArticleListItem;
  priority?: boolean;
}) {
  return (
    <article className="sl-article-card">
      <Link href={`/articles/${encodeURIComponent(article.slug)}`}>
        <div className="sl-card-image">
          {article.featured_image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={normalizeMediaUrl(article.featured_image)}
              alt={article.title}
              width={600}
              height={340}
              loading={priority ? "eager" : "lazy"}
              fetchPriority={priority ? "high" : "auto"}
            />
          ) : (
            <div className="sl-card-placeholder" aria-hidden="true">
              <BookOpen size={48} />
              <span>{article.category?.name || "Storyloom journal"}</span>
            </div>
          )}
          <span className="sl-card-arrow">
            <ArrowUpRight size={19} />
          </span>
        </div>
        <div className="sl-card-body">
          <div className="sl-card-meta">
            <span>{article.category?.name || "STORYLOOM"}</span>
            <span>{article.reading_time} MIN READ</span>
          </div>
          <h3>{article.title}</h3>
          {article.excerpt && <p>{article.excerpt}</p>}
          <div className="sl-card-byline">
            <span className="sl-author-initial" aria-hidden="true">
              {article.author.name.charAt(0)}
            </span>
            <span>{article.author.name}</span>
            {article.published_at && (
              <time dateTime={article.published_at}>
                {new Date(article.published_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </time>
            )}
          </div>
        </div>
      </Link>
    </article>
  );
}
