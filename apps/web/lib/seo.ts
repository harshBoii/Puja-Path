import type { Metadata } from "next";

import { LOCALES } from "@/i18n/config";

export const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/** canonical + hreflang alternates for the locales this page exists in, plus x-default. */
export function alternates(locale: string, path: string, locales: readonly string[] = LOCALES): Metadata["alternates"] {
  const languages: Record<string, string> = {};
  for (const l of locales) languages[l] = `${SITE}/${l}${path}`;
  languages["x-default"] = `${SITE}/${locales.includes("en") ? "en" : locales[0]}${path}`;
  return { canonical: `${SITE}/${locale}${path}`, languages };
}

export function breadcrumbs(items: { name: string; url: string }[]) {
  return {
    "@context": "https://schema.org", "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({ "@type": "ListItem", position: i + 1, name: it.name, item: `${SITE}${it.url}` })),
  };
}

export function faqPage(faqs: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org", "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
  };
}
