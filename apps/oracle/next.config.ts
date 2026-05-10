import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@vantio/agent-sdk"],
  output: "standalone",
};

export default nextConfig;
