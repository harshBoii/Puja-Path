import { TempleCard } from "@pujapath/ui";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { getTemples } from "@/lib/api";
import { alternates } from "@/lib/seo";

export const revalidate = 60;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale });
  return { title: t("meta.templesTitle"), alternates: alternates(locale, "/temples") };
}

export default async function TemplesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, temples] = await Promise.all([getTranslations(), getTemples(locale)]);
  return (
    <div className="pp-gutter pt-6">
      <h1 className="text-h1">{t("meta.templesTitle")}</h1>
      <ul className="mt-6 flex flex-wrap gap-4">
        {(temples ?? []).map((tp) => (
          <li key={tp.id}><TempleCard href={`/temples/${tp.id}-${tp.slug}`} image={tp.photo} name={tp.name} city={tp.city}
            venue={t(`venue.${tp.venue_type}` as "venue.temple")} /></li>
        ))}
      </ul>
    </div>
  );
}
