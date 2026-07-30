import path from "node:path";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(process.cwd(), ".."),
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
