"use client";

import { Heart, MessageCircle, Repeat2, Send, ThumbsUp } from "lucide-react";

import { truncateGraphemes } from "@/lib/graphemes";
import type { Platform } from "@/lib/studio-api";

/**
 * Faithful platform preview cards.
 *
 * Not schematic mock-ups. The point is that an editor can *trust* what they
 * see, and the details that make a real post read differently from a draft are
 * exactly the ones a schematic drops: LinkedIn hides everything past ~140
 * characters behind “…see more”, Facebook past ~250, and X shows the whole
 * thing but shortens every link to a t.co stub of fixed width.
 *
 * Those cut points are where a caption's meaning actually lives — a post whose
 * first sentence is a preamble reads as empty in the feed, and nothing but a
 * faithful preview shows that before it is published.
 */

const SEE_MORE_AT: Partial<Record<Platform, number>> = {
  linkedin: 140,
  facebook: 250,
};

export function SocialPreview({
  platform,
  caption,
  accountName,
  handle,
  avatarUrl,
  media = [],
}: {
  platform: Platform;
  caption: string;
  accountName: string;
  handle?: string;
  avatarUrl?: string;
  media?: Array<{ url: string; alt?: string }>;
}) {
  const cutAt = SEE_MORE_AT[platform];
  const shown = cutAt ? truncateGraphemes(caption, cutAt) : caption;
  const truncated = shown.length < caption.length;

  const Chrome = CHROME[platform] ?? CHROME.x;

  return (
    <Chrome
      accountName={accountName}
      handle={handle}
      avatarUrl={avatarUrl}
      media={media}
    >
      <p className="whitespace-pre-wrap break-words">
        {renderCaption(shown, platform)}
        {truncated && (
          <span className="text-[var(--sl-muted)]">
            … <span className="cursor-pointer hover:underline">see more</span>
          </span>
        )}
      </p>
    </Chrome>
  );
}

/**
 * Links styled the way each platform shows them.
 *
 * X replaces every URL with a shortened stub, which is *why* it charges a flat
 * 23 characters. Showing the raw URL in the preview would make the counter look
 * wrong to anyone comparing the two.
 */
function renderCaption(text: string, platform: Platform) {
  const parts = text.split(/(https?:\/\/\S+)/g);
  return parts.map((part, index) => {
    if (!/^https?:\/\//.test(part)) return <span key={index}>{part}</span>;
    const display =
      platform === "x"
        ? part.replace(/^https?:\/\//, "").slice(0, 20) + (part.length > 27 ? "…" : "")
        : part;
    return (
      <span key={index} className="text-[#1d9bf0] dark:text-[#6bb9f0]">
        {display}
      </span>
    );
  });
}

interface ChromeProps {
  accountName: string;
  handle?: string;
  avatarUrl?: string;
  media?: Array<{ url: string; alt?: string }>;
  children: React.ReactNode;
}

function Avatar({ url, name }: { url?: string; name: string }) {
  if (url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt="" className="h-10 w-10 shrink-0 rounded-full object-cover" />;
  }
  return (
    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--sl-soft)] text-sm font-semibold text-[var(--sl-ink)]">
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

function MediaStrip({ media }: { media?: Array<{ url: string; alt?: string }> }) {
  if (!media?.length) return null;
  return (
    <div
      className={`mt-2 grid gap-0.5 overflow-hidden rounded-xl ${
        media.length === 1 ? "grid-cols-1" : "grid-cols-2"
      }`}
    >
      {media.slice(0, 4).map((item, index) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={index}
          src={item.url}
          alt={item.alt ?? ""}
          className="aspect-video w-full object-cover"
        />
      ))}
    </div>
  );
}

const CHROME: Record<Platform, (props: ChromeProps) => React.JSX.Element> = {
  x: ({ accountName, handle, avatarUrl, media, children }) => (
    <article className="rounded-2xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-4 text-[15px] leading-5 text-[var(--sl-ink)] dark:bg-black">
      <div className="flex gap-3">
        <Avatar url={avatarUrl} name={accountName} />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] leading-5">
            <span className="font-bold">{accountName}</span>{" "}
            <span className="text-[var(--sl-muted)]">{handle || ""} · now</span>
          </p>
          <div className="mt-0.5">{children}</div>
          <MediaStrip media={media} />
          <div className="mt-3 flex max-w-[280px] justify-between text-[var(--sl-muted)]">
            <MessageCircle size={16} />
            <Repeat2 size={16} />
            <Heart size={16} />
            <Send size={16} />
          </div>
        </div>
      </div>
    </article>
  ),

  linkedin: ({ accountName, handle, avatarUrl, media, children }) => (
    <article className="rounded-lg border border-[var(--sl-line)] bg-[var(--sl-card)] text-[14px] leading-5 text-[var(--sl-ink)]">
      <div className="flex gap-2 p-3">
        <Avatar url={avatarUrl} name={accountName} />
        <div className="min-w-0">
          <p className="text-sm font-semibold">{accountName}</p>
          <p className="text-xs text-[var(--sl-muted)]">{handle || "Author"} · now</p>
        </div>
      </div>
      <div className="px-3 pb-2">{children}</div>
      <MediaStrip media={media} />
      <div className="mt-1 flex justify-around border-t border-[var(--sl-line)] py-1.5 text-xs font-medium text-[var(--sl-muted)]">
        <span className="flex items-center gap-1">
          <ThumbsUp size={14} /> Like
        </span>
        <span className="flex items-center gap-1">
          <MessageCircle size={14} /> Comment
        </span>
        <span className="flex items-center gap-1">
          <Repeat2 size={14} /> Repost
        </span>
      </div>
    </article>
  ),

  facebook: ({ accountName, avatarUrl, media, children }) => (
    <article className="rounded-lg border border-[var(--sl-line)] bg-[var(--sl-card)] text-[15px] leading-5 text-[var(--sl-ink)]">
      <div className="flex gap-2 p-3">
        <Avatar url={avatarUrl} name={accountName} />
        <div>
          <p className="text-sm font-semibold">{accountName}</p>
          <p className="text-xs text-[var(--sl-muted)]">Just now · 🌐</p>
        </div>
      </div>
      <div className="px-3 pb-2">{children}</div>
      <MediaStrip media={media} />
      <div className="mt-1 flex justify-around border-t border-[var(--sl-line)] py-1.5 text-sm font-medium text-[var(--sl-muted)]">
        <span>Like</span>
        <span>Comment</span>
        <span>Share</span>
      </div>
    </article>
  ),

  threads: ({ accountName, handle, avatarUrl, media, children }) => (
    <article className="rounded-2xl border border-[var(--sl-line)] bg-[var(--sl-card)] p-4 text-[15px] leading-5 text-[var(--sl-ink)] dark:bg-black">
      <div className="flex gap-3">
        <Avatar url={avatarUrl} name={accountName} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">
            {handle || accountName}
            <span className="ml-2 font-normal text-[var(--sl-muted)]">now</span>
          </p>
          <div className="mt-0.5">{children}</div>
          <MediaStrip media={media} />
          <div className="mt-3 flex gap-4 text-[var(--sl-muted)]">
            <Heart size={17} />
            <MessageCircle size={17} />
            <Repeat2 size={17} />
            <Send size={17} />
          </div>
        </div>
      </div>
    </article>
  ),
};
