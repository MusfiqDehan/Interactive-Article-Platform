"use client";

import {
  BarChart3,
  CalendarDays,
  FileText,
  FolderTree,
  Image as ImageIcon,
  LayoutDashboard,
  Search,
  Send,
  Settings,
  Share2,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  AdminShell,
  type AdminNavItem,
} from "@/components/storyloom/AdminShell";
import { StudioTopBar } from "@/components/studio/StudioTopBar";
import { useAuth } from "@/lib/auth";

const NAV: AdminNavItem[] = [
  {
    href: "/studio",
    label: "Overview",
    group: "Workspace",
    icon: LayoutDashboard,
    exact: true,
  },
  {
    href: "/studio/content",
    label: "Content",
    group: "Workspace",
    icon: FileText,
  },
  {
    href: "/studio/calendar",
    label: "Calendar",
    group: "Workspace",
    icon: CalendarDays,
  },
  {
    href: "/studio/review",
    label: "Review",
    group: "Workspace",
    icon: ShieldCheck,
  },
  { href: "/studio/media", label: "Media", group: "Library", icon: ImageIcon },
  {
    href: "/studio/taxonomy",
    label: "Taxonomy",
    group: "Library",
    icon: FolderTree,
  },
  { href: "/studio/seo", label: "SEO", group: "Reach", icon: Search },
  {
    href: "/studio/distribution",
    label: "Distribution",
    group: "Reach",
    icon: Send,
  },
  { href: "/studio/social", label: "Social", group: "Reach", icon: Share2 },
  {
    href: "/studio/analytics",
    label: "Analytics",
    group: "Reach",
    icon: BarChart3,
  },
  { href: "/studio/people", label: "People", group: "Manage", icon: Users },
  {
    href: "/studio/settings",
    label: "Settings",
    group: "Manage",
    icon: Settings,
  },
];

export default function StudioLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!isLoading && !user) router.replace("/login");
  }, [isLoading, user, router]);
  // Membership remains enforced by the API, rather than the global user role.
  if (isLoading || !user)
    return (
      <div className="sl-shell sl-admin-loading" role="status">
        Opening your workspace…
      </div>
    );
  return (
    <AdminShell items={NAV} toolbar={<StudioTopBar />}>
      {children}
    </AdminShell>
  );
}
