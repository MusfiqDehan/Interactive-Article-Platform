import Link from "next/link";
import { ArrowRight, BookOpen } from "lucide-react";
import type { ReactNode } from "react";

export function PageIntro({
  eyebrow,
  title,
  accent,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  accent: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <header className="sl-page-intro">
      <div>
        <span className="sl-eyebrow">{eyebrow}</span>
        <h1>
          {title} <em>{accent}</em>
        </h1>
        <p>{description}</p>
      </div>
      {children}
    </header>
  );
}

export function EmptyState({
  title,
  description,
  href,
  action,
}: {
  title: string;
  description: string;
  href?: string;
  action?: string;
}) {
  return (
    <div className="sl-empty">
      <span className="sl-empty-icon">
        <BookOpen size={27} />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {href && (
        <Link className="sl-button sl-button-outline" href={href}>
          {action}
          <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}

export function DiscoveryBanner() {
  return (
    <aside className="sl-discovery-banner">
      <div>
        <span className="sl-eyebrow">THERE’S ALWAYS ANOTHER LAYER</span>
        <h2>Follow your curiosity.</h2>
        <p>Explore the ideas, details, and perspectives behind every story.</p>
      </div>
      <Link href="/articles" className="sl-button">
        Explore articles <ArrowRight size={16} />
      </Link>
    </aside>
  );
}
