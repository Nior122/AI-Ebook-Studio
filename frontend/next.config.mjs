import path from "node:path";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // OpenNext expects the standalone app at `.next/standalone/.next`. Keep its
  // trace root at the frontend package; standard Next builds can still trace
  // across the repository root for sibling workspace files.
  outputFileTracingRoot:
    process.env.NEXT_PRIVATE_STANDALONE === "true"
      ? process.cwd()
      : path.join(process.cwd(), ".."),
  experimental: {
    externalDir: true,
  },
  async redirects() {
    return [];
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8765"}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
