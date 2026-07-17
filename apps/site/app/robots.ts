import type { MetadataRoute } from "next";

// Nothing on this marketing site is behind auth or sensitive -- unlike
// ../Resilinked's apps/web, there's no login/dashboard/draft-legal-content
// to disallow here, so this stays a simple allow-everything policy.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.corroborly.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
