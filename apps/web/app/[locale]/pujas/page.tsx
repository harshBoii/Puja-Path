import { EmptyState } from "@pujapath/ui";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import JsonLd from "@/components/JsonLd";
import Filters from "@/components/listing/Filters";
import LoadMore from "@/components/listing/LoadMore";
import { getHome, getPujas, getTemples } from "@/lib/api";
import { alternates, breadcrumbs } from "@/lib/seo";

export const revalidate = 60;
const KEYS = ["deity", "dosha", "benefit", "temple", "date", "q", "sort"] as const;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale });
  return { title: t("meta.listingTitle"), description: t("listing.subtitle"), alternates: alternates(locale, "/pujas") };
}

export default async function PujasPage({ params, searchParams }: {
  params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const sp = await searchParams;
  const qs = new URLSearchParams();
  for (const k of KEYS) if (sp[k]) qs.set(k, sp[k]!);
  const [t, data, home, temples] = await Promise.all([
    getTranslations(), getPujas(locale, qs.toString()), getHome(locale), getTemples(locale),
  ]);
  const tag = (k: string) => t(`tags.${k}` as "tags.shiva");
  const groups = [
    { key: "deity", label: t("listing.filterDeity"), options: (home?.tags.deity ?? []).map((v) => ({ value: v, label: tag(v) })) },
    { key: "dosha", label: t("listing.filterDosha"), options: (home?.tags.dosha ?? []).map((v) => ({ value: v, label: tag(v) })) },
    { key: "benefit", label: t("listing.filterBenefit"), options: (home?.tags.benefit ?? []).map((v) => ({ value: v, label: tag(v) })) },
    { key: "temple", label: t("listing.filterTemple"), options: (temples ?? []).map((tp) => ({ value: String(tp.id), label: tp.name })) },
    { key: "date", label: t("listing.filterDate"), options: [
      { value: "this_week", label: t("listing.thisWeek") }, { value: "next_week", label: t("listing.nextWeek") },
      { value: "festival", label: t("listing.festival") }] },
  ];
  return (
    <div className="pp-gutter pt-6">
      <JsonLd data={breadcrumbs([{ name: t("nav.home"), url: `/${locale}` }, { name: t("listing.title"), url: `/${locale}/pujas` }])} />
      <h1 className="text-h1">{t("listing.title")}</h1>
      <p className="mt-1 text-ink-600">{t("listing.subtitle")}</p>
      <div className="mt-5">
        <Suspense>
          <Filters groups={groups} sortOptions={[
            { value: "soonest", label: t("listing.sortSoonest") }, { value: "price", label: t("listing.sortPrice") },
            { value: "popular", label: t("listing.sortPopular") }]}
            labels={{ filters: t("common.filters"), apply: t("common.apply"), clear: t("common.clear"), close: t("common.close"),
              sort: t("common.sort"), search: t("common.search"), placeholder: t("common.searchPlaceholder") }} />
        </Suspense>
      </div>
      <p className="my-4 text-small text-ink-600" aria-live="polite">{t("listing.results", { count: data?.total ?? 0 })}</p>
      {data && data.items.length ? (
        <LoadMore key={qs.toString()} endpoint={`/${locale}/pujas`} query={qs.toString()} initial={data}
          labels={{ more: t("common.loadMore"), done: t("common.seenAll", { count: data.total }), error: t("common.error") }} />
      ) : <EmptyState title={t("listing.empty")} />}
    </div>
  );
}
