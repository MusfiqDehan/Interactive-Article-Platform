"use client";

import { Eye, EyeOff, FilePenLine } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/primitives";
import type { AvailableTransition, StudioStatus } from "@/lib/studio-api";
import { cn } from "@/lib/cn";

/**
 * Customer-facing visibility: Draft, Public, Hidden.
 *
 * The editorial machine has more states (review, scheduled). Those still show
 * on the status badge. This control answers the only question a publisher
 * actually asks: is this live, in progress, or taken down?
 */

type Visibility = "draft" | "public" | "hidden";

const OPTIONS: {
  id: Visibility;
  label: string;
  hint: string;
  Icon: typeof Eye;
}[] = [
  { id: "draft", label: "Draft", hint: "Only visible in the studio", Icon: FilePenLine },
  { id: "public", label: "Public", hint: "Live on the site", Icon: Eye },
  { id: "hidden", label: "Hidden", hint: "Taken off the site", Icon: EyeOff },
];

function visibilityOf(status: StudioStatus): Visibility {
  if (status === "published") return "public";
  if (status === "archived") return "hidden";
  return "draft";
}

function transitionFor(from: StudioStatus, to: Visibility): string | null {
  if (to === "public") return from === "published" ? null : "publish";
  if (to === "hidden") return from === "archived" ? null : "archive";
  if (from === "published") return "unpublish";
  if (from === "archived") return "restore";
  if (from === "in_review") return "withdraw";
  return null;
}

export function VisibilityControl({
  status,
  transitions,
  busy,
  onRun,
}: {
  status: StudioStatus;
  transitions: AvailableTransition[];
  busy: boolean;
  onRun: (name: string) => void;
}) {
  const current = visibilityOf(status);
  const names = new Set(transitions.map((item) => item.name));
  const currentOption = OPTIONS.find((item) => item.id === current) ?? OPTIONS[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={busy}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold",
          current === "public" &&
            "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300",
          current === "hidden" &&
            "border-stone-300 bg-stone-100 text-stone-700 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300",
          current === "draft" &&
            "border-[var(--sl-line)] bg-[var(--sl-card)] text-[var(--sl-ink)]",
        )}
        aria-label="Article visibility"
      >
        <currentOption.Icon size={13} />
        {currentOption.label}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Visibility</DropdownMenuLabel>
        {OPTIONS.map((option) => {
          const name = transitionFor(status, option.id);
          const available = name === null || names.has(name);
          return (
            <DropdownMenuItem
              key={option.id}
              disabled={!available || busy || option.id === current}
              onSelect={() => {
                if (name) onRun(name);
              }}
            >
              <option.Icon size={14} />
              <span className="flex flex-col">
                <span>{option.label}</span>
                <span className="text-[11px] font-normal text-[var(--sl-muted)]">{option.hint}</span>
              </span>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
