import type { Metadata } from "next";
import type { ReactNode } from "react";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Sign In",
  description: "Sign in to your Vantio AI account.",
  path: "/login",
  noindex: true,
});

// The login page builds its Supabase client at render time from runtime env
// vars, so it must render dynamically rather than be prerendered at build.
export const dynamic = "force-dynamic";

export default function LoginLayout({ children }: { children: ReactNode }) {
  return children;
}
