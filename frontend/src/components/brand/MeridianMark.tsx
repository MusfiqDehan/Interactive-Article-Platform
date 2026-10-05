import { cn } from "@/lib/cn";

/** Meridian's mark: a globe with one living meridian. */
export function MeridianMark({
  className,
  size = 36,
  title = "Meridian",
}: {
  className?: string;
  size?: number;
  title?: string;
}) {
  const uid = "meridian-mark";

  return (
    <svg
      viewBox="0 0 40 40"
      width={size}
      height={size}
      className={cn("shrink-0", className)}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <defs>
        <linearGradient id={`${uid}-bg`} x1="8" y1="2" x2="34" y2="38" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1c1917" />
          <stop offset="1" stopColor="#292524" />
        </linearGradient>
        <linearGradient id={`${uid}-gold`} x1="20" y1="4" x2="20" y2="36" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fde68a" />
          <stop offset="1" stopColor="#d97706" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="38" height="38" rx="10" fill={`url(#${uid}-bg)`} />
      <rect x="1" y="1" width="38" height="38" rx="10" fill="none" stroke="rgba(251,191,36,0.35)" />
      <circle cx="20" cy="20" r="11.5" fill="none" stroke="rgba(253,230,138,0.35)" strokeWidth="1" />
      <ellipse cx="20" cy="20" rx="5.5" ry="11.5" fill="none" stroke="rgba(253,230,138,0.22)" strokeWidth="0.8" />
      <ellipse cx="20" cy="20" rx="11.5" ry="4.2" fill="none" stroke="rgba(253,230,138,0.22)" strokeWidth="0.8" />
      <path
        d="M20 8.5 C 24.8 12.2 24.8 27.8 20 31.5 C 15.2 27.8 15.2 12.2 20 8.5 Z"
        fill="none"
        stroke={`url(#${uid}-gold)`}
        strokeWidth="1.7"
        strokeLinecap="round"
      >
        <animate
          attributeName="opacity"
          values="0.55;1;0.55"
          dur="2.4s"
          repeatCount="indefinite"
        />
      </path>
      <circle cx="20" cy="8.5" r="1.3" fill="#fde68a">
        <animate attributeName="cy" values="8.5;31.5;8.5" dur="3.2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="1;0.4;1" dur="3.2s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}
