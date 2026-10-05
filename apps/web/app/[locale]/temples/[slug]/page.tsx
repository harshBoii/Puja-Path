import { IconMapPin, SectionTitle, VenueBadge } from "@pujapath/ui";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import JsonLd from "@/components/JsonLd";
import PujaCardItem from "@/components/PujaCardItem";
import { getTemple } from "@/lib/api";
import { dateIST, idFromSlug } from "@/lib/format";
import { alternates, breadcrumbs } from "@/lib/seo";
import { Paragraphs } from "@/lib/text";

export const revalidate = 300;
export const generateStaticParams = () => [];

type Props = { params: Promise<{ locale: string; slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  const id = idFromSlug(slug);
  const tp = id ? await getTemple(locale, id) : null;
  if (!tp) return {};
  return { title: `${tp.name}, ${tp.city}`, description: tp.history_md?.slice(0, 160),
    alternates: alternates(locale, `/temples/${tp.id}-${tp.slug}`, tp.available_locales) };
}

export default async function TemplePage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const id = idFromSlug(slug);
  const tp = id ? await getTemple(locale, id) : null;
  if (!tp) notFound();
  const t = await getTranslations();
  return (
    <div className="pp-gutter pt-6">
      <JsonLd data={breadcrumbs([{ name: t("nav.home"), url: `/${locale}` }, { name: t("nav.temples"), url: `/${locale}/temples` },
        { name: tp.name, url: `/${locale}/temples/${tp.id}-${tp.slug}` }])} />
      <div className="grid gap-6 md:grid-cols-[1fr_1fr]">
        <div className="space-y-3">
          <h1 className="pp-foil-text text-display">{tp.name}</h1>
          <p className="flex flex-wrap items-center gap-2 text-ink-600">
            <IconMapPin className="text-gold-700" /> {tp.city}, {tp.state} <VenueBadge label={t(`venue.${tp.venue_type}` as "venue.temple")} />
          </p>
          {/* presiding_deity is a language-neutral field; shown only where it matches the page's script */}
          {locale === "en" && <p>{t("puja.presidingDeity")}: <strong>{tp.presiding_deity}</strong></p>}
          {tp.address && <p className="text-small text-ink-600">{tp.address}</p>}
          <Paragraphs text={tp.history_md} />
          {tp.lat && tp.lng && (
            <a className="pp-link inline-flex min-h-12 items-center" target="_blank" rel="noopener noreferrer"
              href={`https://www.google.com/maps/search/?api=1&query=${tp.lat},${tp.lng}`}>{t("puja.mapLink")}</a>
          )}
        </div>
        <ul className="grid grid-cols-2 gap-3">
          {tp.photos.filter(Boolean).map((ph, i) => (
            <li key={i}><figure className="pp-card overflow-hidden">
              <img src={ph!.url} alt={ph!.alt} loading={i ? "lazy" : "eager"} className="aspect-square w-full object-cover" />
              {ph!.taken_on && <figcaption className="p-2 text-small text-ink-600">{dateIST(ph!.taken_on, locale, { year: "numeric" })}</figcaption>}
            </figure></li>
          ))}
        </ul>
      </div>
      <section className="mt-10" aria-labelledby="tp-pujas">
        <SectionTitle id="tp-pujas">{t("nav.pujas")}</SectionTitle>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tp.pujas.map((p) => <li key={p.id}><PujaCardItem p={p} /></li>)}
        </ul>
      </section>
    </div>
  );
}
