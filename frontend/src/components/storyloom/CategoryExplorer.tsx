"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowUpRight,
  Search,
  BookOpen,
  Compass,
  Layers3,
  Globe2,
  Sparkles,
  Shapes,
} from "lucide-react";
import type { PublicCategory } from "@/lib/public-types";
import { EmptyState } from "./Primitives";

const icons = [Compass, Layers3, Globe2, Sparkles, Shapes, BookOpen];

export function CategoryExplorer({
  categories,
}: {
  categories: PublicCategory[];
}) {
  const [query, setQuery] = useState("");
  const visible = categories.filter((c) =>
    `${c.name} ${c.description}`
      .toLocaleLowerCase()
      .includes(query.trim().toLocaleLowerCase()),
  );
  return (
    <>
      <div className="sl-category-toolbar">
        <div>
          <span className="sl-eyebrow">THE TOPIC COLLECTION</span>
          <p role="status">
            {visible.length} {visible.length === 1 ? "topic" : "topics"} to
            explore
          </p>
        </div>
        <div className="sl-search sl-topic-search">
          <Search size={18} />
          <label className="sr-only" htmlFor="category-search">
            Find a topic
          </label>
          <input
            id="category-search"
            type="search"
            placeholder="Find your next interest…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>
      {visible.length ? (
        <div className="sl-category-grid">
          {visible.map((category) => {
            const Icon = icons[category.id % icons.length];
            return (
              <Link
                className={`sl-category-card sl-tone-${category.id % 3}`}
                key={category.id}
                href={`/categories/${encodeURIComponent(category.slug)}`}
              >
                <div className="sl-category-top">
                  <span className="sl-category-icon">
                    <Icon size={28} strokeWidth={1.4} />
                  </span>
                  <ArrowUpRight size={22} />
                </div>
                <h2>{category.name}</h2>
                <p>
                  {category.description ||
                    `Ideas, stories, and new perspectives in ${category.name}.`}
                </p>
                <div className="sl-category-bottom">
                  <span>
                    {category.article_count ?? 0}{" "}
                    {category.article_count === 1 ? "article" : "articles"}
                  </span>
                  <span>
                    Explore topic <ArrowUpRight size={14} />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      ) : (
        <>
          <EmptyState
            title={
              query
                ? "A different word might open a door."
                : "New perspectives are on their way."
            }
            description={
              query
                ? `No topics match “${query}”. Try a broader search.`
                : "Topics will appear here as the journal grows. In the meantime, explore the articles."
            }
            href={query ? undefined : "/articles"}
            action="Browse articles"
          />
          {query && (
            <button
              className="sl-button sl-clear-topic"
              onClick={() => setQuery("")}
            >
              Clear search
            </button>
          )}
        </>
      )}
    </>
  );
}
