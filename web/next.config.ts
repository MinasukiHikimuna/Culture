import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["culture.chiefsclub.com"],
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/releases/**",
      },
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/performers/**",
      },
      {
        protocol: "https",
        hostname: "cdn.stashdb.org",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
