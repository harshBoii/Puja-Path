import { Accordion } from "@pujapath/ui";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import JsonLd from "@/components/JsonLd";
import { getConfig, getFaqs } from "@/lib/api";
import { renderTokens, supportDays } from "@/lib/format";
import { alternates, faqPage } from "@/lib/seo";

export const revalidate = 300;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale });
  return { title: t("pages.faqTitle"), alternates: alternates(locale, "/faq") };
}

export default async function Faq({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, c, faqs] = await Promise.all([getTranslations(), getConfig(), getFaqs(locale)]);
  const tokens = { video_sla_hours: c.video_sla_hours_default, booking_cutoff_hours: c.booking_cutoff_hours_default,
    refund_days: c.refund_expected_days, gotra_fallback: c.gotra_fallback[locale] ?? c.gotra_fallback.en,
    support_hours: `${supportDays(c.support_hours.days, locale)} ${c.support_hours.start}–${c.support_hours.end} IST` };
  const items = (faqs ?? []).map((f) => ({ q: f.q, a: renderTokens(f.a, tokens) }));
  return (
    <div className="pp-gutter max-w-3xl pt-6">
      {items.length > 0 && <JsonLd data={faqPage(items)} />}
      <h1 className="mb-6 text-h1">{t("pages.faqTitle")}</h1>
      <Accordion items={items} />
    </div>
  );
}
