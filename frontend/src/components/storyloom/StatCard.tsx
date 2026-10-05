import Link from "next/link";
import { ArrowUpRight, type LucideIcon } from "lucide-react";

export function StatCard({
  icon: Icon,
  label,
  value,
  href,
  detail,
}: {
  icon: LucideIcon;
  label: string;
  value: number | string;
  href: string;
  detail: string;
}) {
  return (
    <Link href={href} className="sl-admin-stat">
      <div>
        <span>
          <Icon size={19} />
        </span>
        <ArrowUpRight size={17} />
      </div>
      <strong>{value}</strong>
      <h2>{label}</h2>
      <p>{detail}</p>
    </Link>
  );
}
