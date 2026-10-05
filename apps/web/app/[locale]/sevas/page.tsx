import { EmptyState } from "@pujapath/ui";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import JsonLd from "@/components/JsonLd";
import Link from "@/components/Link";
import LoadMore from "@/components/listing/LoadMore";
import { getSevas } from "@/lib/api";
import { alternates, breadcrumbs } from "@/lib/seo";

export const revalidate = 60;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale });
  return { title: t("meta.sevasTitle"), description: t("listing.sevasSubtitle"), alternates: alternates(locale, "/sevas") };
}

export default async function SevasPage({ params, searchParams }: {
  params: Promise<{ locale: string }>; searchParams: Promise<{ freq?: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const freq = (await searchParams).freq;
  const valid = freq === "daily" || freq === "weekly" || freq === "monthly" ? freq : undefined;
  const qs = valid ? `freq=${valid}` : "";
  const [t, data] = await Promise.all([getTranslations(), getSevas(locale, qs)]);
  const tabs = [
    { v: undefined, label: t("listing.allSevas") }, { v: "daily", label: t("listing.daily") },
    { v: "weekly", label: t("listing.weekly") }, { v: "monthly", label: t("listing.monthly") },
  ];
  return (
    <div className="pp-gutter pt-6">
      <JsonLd data={breadcrumbs([{ name: t("nav.home"), url: `/${locale}` }, { name: t("listing.sevasTitle"), url: `/${locale}/sevas` }])} />
      <h1 className="text-h1">{t("listing.sevasTitle")}</h1>
      <p className="mt-1 text-ink-600">{t("listing.sevasSubtitle")}</p>
      <nav aria-label={t("listing.sevasTitle")} className="pp-scroll-x -mx-4 mt-5 flex gap-2 px-4">
        {tabs.map((tab) => (
          <Link key={tab.label} href={tab.v ? `/sevas?freq=${tab.v}` : "/sevas"} className="pp-chip no-underline"
            aria-current={valid === tab.v ? "true" : undefined}>{tab.label}</Link>
        ))}
      </nav>
      <div className="mt-6">
        {data && data.items.length ? (
          <LoadMore key={qs} endpoint={`/${locale}/sevas`} query={qs} initial={data}
            labels={{ more: t("common.loadMore"), done: t("common.seenAll", { count: data.total }), error: t("common.error") }} />
        ) : <EmptyState title={t("listing.empty")} />}
      </div>
    </div>
  );
}
