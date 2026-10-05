import type { MetadataRoute } from "next";

import { SITE } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  if (process.env.APP_ENV === "staging") return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/admin", "/api/", "/*/checkout/", "/*/account", "/*/proof/", "/*/bookings/", "/*/preview/"] },
    sitemap: `${SITE}/sitemap.xml`,
  };
}
