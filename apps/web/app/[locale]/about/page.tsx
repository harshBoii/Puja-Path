import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { getConfig } from "@/lib/api";
import { alternates } from "@/lib/seo";
import { Paragraphs } from "@/lib/text";

export const revalidate = 3600;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const [t, c] = await Promise.all([getTranslations({ locale }), getConfig()]);
  return { title: t("pages.aboutTitle", { brand: c.brand }), alternates: alternates(locale, "/about") };
}

export default async function About({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, c] = await Promise.all([getTranslations(), getConfig()]);
  return (
    <article className="pp-gutter max-w-3xl pt-6">
      <h1 className="text-h1">{t("pages.aboutTitle", { brand: c.brand })}</h1>
      <Paragraphs className="mt-4" text={t("pages.aboutBody", { brand: c.brand })} />
    </article>
  );
}
