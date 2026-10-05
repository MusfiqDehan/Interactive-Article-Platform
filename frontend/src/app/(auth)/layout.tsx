import Header from "@/components/layout/Header";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Your account",
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="sl-shell min-h-screen flex flex-col">
      <Header />
      <main className="sl-auth-main">{children}</main>
    </div>
  );
}
