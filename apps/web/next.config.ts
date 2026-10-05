import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const isStaging = process.env.APP_ENV === "staging";

const config: NextConfig = {
  transpilePackages: ["@pujapath/ui", "@pujapath/locales"],
  poweredByHeader: false,
  images: { unoptimized: true }, // R2 + Cloudflare image resizing serve variants (PRD §3)
  async rewrites() {
    // The browser talks only to this app; this app talks to the API (PRD §3).
    return [
      { source: "/api/v1/:path*", destination: `${API_URL}/v1/:path*` },
      { source: "/media/:path*", destination: `${API_URL}/media/:path*` },
    ];
  },
  async headers() {
    const noindex = [{ key: "X-Robots-Tag", value: "noindex, nofollow" }];
    return [
      ...(isStaging ? [{ source: "/:path*", headers: noindex }] : []),
      { source: "/:locale/checkout/:path*", headers: noindex },
      { source: "/:locale/account/:path*", headers: noindex },
      { source: "/:locale/proof/:path*", headers: noindex },
      { source: "/:locale/preview/:path*", headers: noindex },
      { source: "/:locale/bookings/:path*", headers: noindex },
      { source: "/admin/:path*", headers: noindex },
    ];
  },
};

export default createNextIntlPlugin("./i18n/request.ts")(config);
