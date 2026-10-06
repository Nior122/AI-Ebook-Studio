import path from "node:path";

const publicApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const configuredBackendUrl =
  process.env.BACKEND_URL?.trim() ||
  (publicApiBaseUrl?.startsWith("http") ? publicApiBaseUrl : undefined);
const backendOrigin = (
  configuredBackendUrl?.replace(/\/api\/v1\/?$/, "") ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

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
        destination: `${backendOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
