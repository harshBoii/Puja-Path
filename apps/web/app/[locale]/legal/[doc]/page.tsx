import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { getConfig } from "@/lib/api";
import { money } from "@/lib/format";
import { alternates } from "@/lib/seo";
import { Paragraphs } from "@/lib/text";

const DOCS = ["terms", "privacy", "refunds", "shipping"] as const;
type Doc = (typeof DOCS)[number];
export const revalidate = 3600;
export const generateStaticParams = () => DOCS.map((doc) => ({ doc }));

export async function generateMetadata({ params }: { params: Promise<{ locale: string; doc: string }> }): Promise<Metadata> {
  const { locale, doc } = await params;
  if (!DOCS.includes(doc as Doc)) return {};
  const t = await getTranslations({ locale });
  return { title: t(`pages.${doc as Doc}Title`), alternates: alternates(locale, `/legal/${doc}`) };
}

/** Legal pages render from site_config, so policy numbers here match FAQ and checkout exactly (PRD §12). */
export default async function Legal({ params }: { params: Promise<{ locale: string; doc: string }> }) {
  const { locale, doc } = await params;
  if (!DOCS.includes(doc as Doc)) notFound();
  setRequestLocale(locale);
  const [t, c] = await Promise.all([getTranslations(), getConfig()]);
  const values = { brand: c.brand, cutoff: c.booking_cutoff_hours_default, refundDays: c.proof_refund_after_days,
    expectedDays: c.refund_expected_days, fee: money(c.shipping_fee.INR, "INR", locale) };
  return (
    <article className="pp-gutter max-w-3xl pt-6">
      <h1 className="text-h1">{t(`pages.${doc as Doc}Title`)}</h1>
      <Paragraphs className="mt-4" text={t(`pages.${doc as Doc}Body`, values)} />
    </article>
  );
}
