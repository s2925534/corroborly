import type { MetadataRoute } from "next";

// Single-page marketing site today -- extend this list if/when dedicated
// pages (e.g. a per-product page) are added.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.corroborly.com";

export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: SITE_URL, changeFrequency: "monthly", priority: 1 }];
}
