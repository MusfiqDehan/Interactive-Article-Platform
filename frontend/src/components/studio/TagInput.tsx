"use client";

import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import { listTags, type TagRow } from "@/lib/studio-api";

/**
 * Combobox for an article's tags.
 *
 * Typing a name that does not exist and pressing Enter creates it — the server
 * resolves unknown names on write. Requiring the tag to exist first would send
 * the author to another screen mid-sentence, which is how taxonomies end up
 * unused.
 *
 * Backspace on an empty input removes the last tag, because that is what every
 * other chip input does and muscle memory is the whole point of a chip input.
 */
export function TagInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const [suggestions, setSuggestions] = useState<TagRow[]>([]);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      listTags(draft ? { search: draft } : {})
        .then((page) => live && setSuggestions(page.results ?? []))
        .catch(() => live && setSuggestions([]));
    }, 200);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [draft]);

  const add = (name: string) => {
    const trimmed = name.trim();
    // Case-insensitive, because the server matches that way too -- otherwise
    // the chip appears and then silently resolves to the existing tag on save.
    if (!trimmed || value.some((tag) => tag.toLowerCase() === trimmed.toLowerCase())) {
      setDraft("");
      return;
    }
    onChange([...value, trimmed]);
    setDraft("");
  };

  const unused = suggestions.filter(
    (tag) => !value.some((chosen) => chosen.toLowerCase() === tag.name.toLowerCase()),
  );

  return (
    <div className="relative">
      <div
        onClick={() => inputRef.current?.focus()}
        className="flex flex-wrap items-center gap-1.5 rounded-lg border border-[var(--sl-line)] bg-[var(--sl-card)] p-1.5 focus-within:ring-2 focus-within:ring-ring"
      >
        {value.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1 rounded bg-[var(--sl-soft)] py-0.5 pl-2 pr-1 text-xs text-[var(--sl-ink)]"
          >
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((t) => t !== tag))}
              aria-label={`Remove ${tag}`}
              className="rounded p-0.5 hover:bg-[var(--sl-soft)] hover:text-[var(--sl-ink)]"
            >
              <X size={11} />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
          placeholder={value.length ? "" : "Add a tag…"}
          className="min-w-[100px] flex-1 border-0 bg-transparent p-0.5 text-sm outline-none"
        />
      </div>

      {open && (draft || unused.length > 0) && (
        <ul className="absolute z-20 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border border-[var(--sl-line)] bg-[var(--sl-card)] py-1 shadow-lg">
          {unused.slice(0, 8).map((tag) => (
            <li key={tag.id}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => add(tag.name)}
                className="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]"
              >
                {tag.name}
                <span className="text-xs text-[var(--sl-muted)]">{tag.usage_count}</span>
              </button>
            </li>
          ))}
          {draft.trim() &&
            !unused.some(
              (tag) => tag.name.toLowerCase() === draft.trim().toLowerCase(),
            ) && (
              <li>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => add(draft)}
                  className={cn(
                    "w-full px-3 py-1.5 text-left text-sm hover:bg-[var(--sl-soft)] hover:bg-[var(--sl-card)]",
                    unused.length > 0 &&
                      "border-t border-[var(--sl-line)]",
                  )}
                >
                  Create “<strong>{draft.trim()}</strong>”
                </button>
              </li>
            )}
        </ul>
      )}
    </div>
  );
}
