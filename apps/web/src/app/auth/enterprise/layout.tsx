import type { Metadata } from "next";
import type { ReactNode } from "react";
import { buildMetadata } from "@/lib/seo";

// Duplicate of the /enterprise marketing content as a lead-capture form;
// kept out of the index to avoid competing with /enterprise.
export const metadata: Metadata = buildMetadata({
  title: "Talk to Enterprise Sales",
  description: "Deploy Vantio's OS-level AI governance inside your own infrastructure. Talk to our enterprise team.",
  path: "/auth/enterprise",
  noindex: true,
});

export default function EnterpriseAuthLayout({ children }: { children: ReactNode }) {
  return children;
}
