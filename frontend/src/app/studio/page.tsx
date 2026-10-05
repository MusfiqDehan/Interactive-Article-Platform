"use client";

import {
  ArrowRight,
  FileText,
  Plus,
  Send,
  ShieldCheck,
  Image,
  CalendarDays,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/studio/StatusBadge";
import { PageShell, QueryState } from "@/components/studio/PageShell";
import { StatCard } from "@/components/storyloom/StatCard";
import { listArticles, type StudioArticleRow } from "@/lib/studio-api";
import { useAuth } from "@/lib/auth";

export default function StudioOverview() {
  const { user } = useAuth();
  const [recent, setRecent] = useState<StudioArticleRow[]>([]);
  const [counts, setCounts] = useState({ review: 0, scheduled: 0, drafts: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listArticles({ page_size: 8, ordering: "-updated_at" }),
      listArticles({ status: "in_review", page_size: 1 }),
      listArticles({ status: "scheduled", page_size: 1 }),
      listArticles({ status: "draft", page_size: 1 }),
    ])
      .then(([latest, review, scheduled, drafts]) => {
        if (!cancelled) {
          setRecent(latest.results);
          setCounts({
            review: review.count,
            scheduled: scheduled.count,
            drafts: drafts.count,
          });
        }
      })
      .catch(() => {
        if (!cancelled)
          setError(
            "We couldn’t load this workspace. Check your connection and site access, then refresh to try again.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return (
    <PageShell
      title={`A new chapter, ${user?.first_name || user?.username || "writer"}.`}
      description="Your stories, your team, and what comes next. All in one place."
      actions={
        <Link className="sl-button" href="/studio/content/new">
          <Plus size={17} />
          Create a story
        </Link>
      }
    >
      <div className="sl-admin-stats">
        <StatCard
          icon={FileText}
          label="Stories in progress"
          value={loading || error ? "—" : counts.drafts}
          href="/studio/content?status=draft"
          detail="Ideas taking shape, one block at a time."
        />
        <StatCard
          icon={ShieldCheck}
          label="Ready for review"
          value={loading || error ? "—" : counts.review}
          href="/studio/content?status=in_review"
          detail="A fresh pair of eyes makes a difference."
        />
        <StatCard
          icon={Send}
          label="On the calendar"
          value={loading || error ? "—" : counts.scheduled}
          href="/studio/content?status=scheduled"
          detail="The next stories ready to meet the world."
        />
      </div>
      <div className="sl-admin-overview-grid">
        <section className="sl-admin-panel">
          <header>
            <div>
              <span className="sl-eyebrow">PICK UP WHERE YOU LEFT OFF</span>
              <h2>On your editorial desk</h2>
            </div>
            <Link href="/studio/content" className="sl-text-link">
              View all
              <ArrowRight size={15} />
            </Link>
          </header>
          <QueryState
            loading={loading}
            error={error}
            isEmpty={!recent.length}
            empty={
              <>
                <p>Your first story starts with an idea.</p>
                <Link href="/studio/content/new" className="sl-text-link">
                  Create a draft <ArrowRight size={14} />
                </Link>
              </>
            }
          >
            <ul className="sl-admin-recent">
              {recent.map((article) => (
                <li key={article.id}>
                  <span className="sl-admin-doc-icon">
                    <FileText size={19} />
                  </span>
                  <Link
                    href={`/studio/content/${encodeURIComponent(article.slug)}`}
                  >
                    {article.title || "Untitled"}
                    <small>
                      Updated{" "}
                      {new Date(article.updated_at).toLocaleDateString()}
                    </small>
                  </Link>
                  <StatusBadge status={article.status} />
                  <ArrowRight size={15} />
                </li>
              ))}
            </ul>
          </QueryState>
        </section>
        <aside className="sl-admin-panel sl-admin-shortcuts">
          <span className="sl-eyebrow">A LITTLE ROOM TO CREATE</span>
          <h2>Make the story yours.</h2>
          <p>
            Bring together the details that turn a good read into a deeper
            discovery.
          </p>
          {[
            {
              href: "/studio/media",
              icon: Image,
              title: "Your media library",
              body: "Find the right image or recording.",
            },
            {
              href: "/studio/calendar",
              icon: CalendarDays,
              title: "Plan what’s next",
              body: "See your publishing schedule.",
            },
            {
              href: "/studio/review",
              icon: ShieldCheck,
              title: "The review desk",
              body: "Give every story a thoughtful check.",
            },
          ].map(({ href, icon: Icon, title, body }) => (
            <Link key={href} href={href}>
              <Icon size={19} />
              <span>
                {title}
                <small>{body}</small>
              </span>
              <ArrowRight size={14} />
            </Link>
          ))}
        </aside>
      </div>
    </PageShell>
  );
}
