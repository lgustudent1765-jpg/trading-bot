import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  typescript: {
    // Auto-generated .next/types files have a conflict with TypeScript 5.9+
    ignoreBuildErrors: true,
  },
  experimental: {
    // Disable worker threads for static generation — works around a
    // workUnitAsyncStorage invariant bug in Next.js 16.1.6 when
    // prerendering /_global-error.
    workerThreads: false,
  },
  async redirects() {
    return [{ source: "/", destination: "/dashboard", permanent: false }];
  },
  async rewrites() {
    const apiUrl = process.env.ALGO_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
