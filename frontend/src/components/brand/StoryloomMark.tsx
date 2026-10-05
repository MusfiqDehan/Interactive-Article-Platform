import Image from "next/image";

import { PLATFORM } from "@/lib/brand";
import { cn } from "@/lib/cn";

/** Shared SVG artwork keeps every product surface in sync. */
export function StoryloomMark({
  className,
  size = 36,
  title = PLATFORM.name,
}: {
  className?: string;
  size?: number;
  title?: string;
}) {
  return (
    <Image
      src="/logo.svg"
      width={size}
      height={size}
      alt={title}
      className={cn("shrink-0", className)}
      unoptimized
    />
  );
}

export function StoryloomWordmark({
  className,
  markSize = 36,
  compact = false,
}: {
  className?: string;
  markSize?: number;
  compact?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <StoryloomMark size={markSize} title={compact ? PLATFORM.name : ""} />
      {!compact && <span>{PLATFORM.name}</span>}
    </span>
  );
}
