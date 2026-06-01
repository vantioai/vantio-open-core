import type { Metadata } from "next";
import type { ReactNode } from "react";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Sign In",
  description: "Sign in to your Vantio AI account.",
  path: "/login",
  noindex: true,
});

export default function LoginLayout({ children }: { children: ReactNode }) {
  return children;
}
