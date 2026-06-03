import type { NextConfig } from "next";

// Note: output: "standalone" is for Docker/self-hosted deployments only.
// Vercel handles its own build pipeline — do not set standalone here.
const nextConfig: NextConfig = {
  // Canonicalize the www host to the bare apex (matches the canonical URLs in
  // metadata). Requires www.vantio.ai to be attached to the Vercel project.
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.vantio.ai" }],
        destination: "https://vantio.ai/:path*",
        permanent: true,
      },
      // Research was renamed to "The Brief". Keep the old URL alive.
      {
        source: "/research",
        destination: "/brief",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
