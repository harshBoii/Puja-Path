import type { MetadataRoute } from "next";

import { LOCALES } from "@/i18n/config";
import { getSitemap } from "@/lib/api";
import { SITE } from "@/lib/seo";

export const revalidate = 300;

/** Generated from the database: every published (page, locale) pair with hreflang alternates. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const data = await getSitemap();
  const entry = (path: string, locales: readonly string[]): MetadataRoute.Sitemap =>
    locales.map((l) => ({
      url: `${SITE}/${l}${path}`,
      alternates: { languages: Object.fromEntries(locales.map((x) => [x, `${SITE}/${x}${path}`])) },
    }));
  const statics = ["", "/pujas", "/sevas", "/temples", "/about", "/faq", "/contact", "/legal/terms", "/legal/privacy",
    "/legal/refunds", "/legal/shipping"].flatMap((p) => entry(p, LOCALES));
  const pujas = (data?.pujas ?? []).filter((p) => p.locales.length)
    .flatMap((p) => entry(`/${p.kind === "seva" ? "sevas" : "pujas"}/${p.id}-${p.slug}`, p.locales));
  const temples = (data?.temples ?? []).flatMap((t) => entry(`/temples/${t.id}-${t.slug}`, t.locales));
  return [...statics, ...pujas, ...temples];
}
