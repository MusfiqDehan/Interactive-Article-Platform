import type { Metadata } from "next";
import { PLATFORM } from "@/lib/brand";

export const metadata: Metadata = {
  title: { absolute: `Create an account | ${PLATFORM.name}` },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
