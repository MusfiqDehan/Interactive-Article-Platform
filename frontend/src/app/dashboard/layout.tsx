"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LayoutDashboard, User, FileText, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";
import ThemeToggle from "@/components/layout/ThemeToggle";
import {
  AdminShell,
  type AdminNavItem,
} from "@/components/storyloom/AdminShell";

const items: AdminNavItem[] = [
  {
    href: "/dashboard",
    label: "Overview",
    icon: LayoutDashboard,
    group: "Your workspace",
    exact: true,
  },
  {
    href: "/dashboard/my-articles",
    label: "My articles",
    icon: FileText,
    group: "Your workspace",
  },
  {
    href: "/dashboard/profile",
    label: "Your profile",
    icon: User,
    group: "Account",
  },
];
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace("/login");
  }, [isLoading, isAuthenticated, router]);
  if (isLoading || !user)
    return (
      <div className="sl-shell sl-admin-loading" role="status">
        Opening your workspace…
      </div>
    );
  return (
    <AdminShell
      items={items}
      label="Your workspace"
      toolbar={
        <header className="sl-admin-topbar">
          <span>Welcome, {user.first_name || user.username}</span>
          <div>
            <ThemeToggle />
            <button
              className="sl-text-link"
              onClick={async () => {
                await logout();
                router.push("/");
              }}
            >
              <LogOut size={16} />
              Sign out
            </button>
          </div>
        </header>
      }
    >
      <div className="sl-admin-page">{children}</div>
    </AdminShell>
  );
}
