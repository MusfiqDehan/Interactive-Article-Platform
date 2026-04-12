import Header from "@/components/layout/Header";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950">
      <Header />
      <main className="flex-1 flex items-center justify-center p-4">{children}</main>
    </div>
  );
}
