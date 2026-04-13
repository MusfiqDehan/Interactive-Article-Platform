import type { Metadata } from "next";
import { Hind_Siliguri } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const hindSiliguri = Hind_Siliguri({
  subsets: ["bengali", "latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-hind-siliguri",
});

export const metadata: Metadata = {
  title: "Interactive Articles - Dynamic Content Platform",
  description:
    "A dynamic, interactive article platform with rich multimedia content, interactive modals, and an engaging reading experience.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${hindSiliguri.variable} font-sans`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
