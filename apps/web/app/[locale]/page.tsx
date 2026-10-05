import {
  Accordion,
  ArchFrame,
  OccasionChip,
  OrnamentDivider,
  PromiseStrip,
  ReviewCard,
  SectionTitle,
  StepsRow,
  TempleCard,
  TrustBar,
  HeroCarousel,
} from "@pujapath/ui";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { WhatsAppButton } from "@/components/Contact";
import JsonLd from "@/components/JsonLd";
import Link from "@/components/Link";
import PujaCardItem from "@/components/PujaCardItem";
import UpcomingTabs from "./_home/UpcomingTabs";
import { getConfig, getHome } from "@/lib/api";
import { dateIST, pujaPath, renderTokens, supportDays } from "@/lib/format";
import { SITE, alternates, breadcrumbs, faqPage } from "@/lib/seo";
import en from "@pujapath/locales/en.json";

export const revalidate = 60;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const [t, config] = await Promise.all([getTranslations({ locale }), getConfig()]);
  const title = t("meta.homeTitle", { brand: config.brand });
  return {
    title: { absolute: title }, description: t("meta.siteDescription"), alternates: alternates(locale, ""),
    openGraph: { title, description: t("meta.siteDescription"), url: `${SITE}/${locale}`, images: ["/og-default.png"] },
  };
}

export default async function Home({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, home, config] = await Promise.all([getTranslations(), getHome(locale), getConfig()]);
  if (!home) return null;
  const tagLabels = Object.fromEntries(Object.keys(en.tags).map((k) => [k, t(`tags.${k}` as "tags.shiva")]));
  const tokens = {
    video_sla_hours: config.video_sla_hours_default, booking_cutoff_hours: config.booking_cutoff_hours_default,
    refund_days: config.refund_expected_days, gotra_fallback: config.gotra_fallback[locale] ?? config.gotra_fallback.en,
    support_hours: `${supportDays(config.support_hours.days, locale)} ${config.support_hours.start}–${config.support_hours.end} IST`,
  };
  const faqs = home.faqs.map((f) => ({ q: f.q, a: renderTokens(f.a, tokens) }));
  const trustItems = home.trust.items.map((it) => ({
    key: it.key,
    text: it.key === "pujas_completed" ? t("home.pujasCompleted", { count: it.value.toLocaleString(locale) })
      : it.key === "devotees" ? t("home.devoteesServed", { count: it.value.toLocaleString(locale) })
        : t("home.rating", { rating: it.value, count: it.count ?? 0 }),
  }));

  const slides = home.hero.map((p, i) => (
    <div key={p.id} className="grid items-center gap-6 md:grid-cols-[1.1fr_1fr]">
      <div className="order-2 md:order-1">
        {p.occasion_chip && <OccasionChip>{p.occasion_chip}</OccasionChip>}
        <h2 className="pp-foil-text mt-3 text-display">{p.title}</h2>
        {p.subtitle && <p className="mt-3 text-h3 font-normal text-ink-600">{p.subtitle}</p>}
        <p className="mt-3 text-ink-600">{p.temple.name} · {p.event ? dateIST(p.event.starts_at, locale) : ""}</p>
        <Link href={pujaPath(p)} className="pp-btn pp-btn-primary mt-5 w-full sm:w-auto">{t("home.heroBook")}</Link>
      </div>
      <div className="order-1 mx-auto w-3/4 max-w-sm md:order-2">
        {p.image && <ArchFrame src={p.image.url} srcSet={p.image.srcset} alt={p.image.alt} priority={i === 0}
          sizes="(min-width: 768px) 400px, 75vw" />}
      </div>
    </div>
  ));

  return (
    <>
      <JsonLd data={[
        { "@context": "https://schema.org", "@type": "Organization", name: config.brand, url: SITE,
          contactPoint: { "@type": "ContactPoint", telephone: config.support_phone_e164, contactType: "customer support",
            availableLanguage: config.support_languages } },
        breadcrumbs([{ name: config.brand, url: `/${locale}` }]),
        ...(faqs.length ? [faqPage(faqs)] : []),
      ]} />
      <section className="pp-marble border-b border-gold-line pb-8 pt-6 md:pt-10">
        <div className="pp-gutter">
          <h1 className="sr-only">{t("meta.homeTitle", { brand: config.brand })}</h1>
          <HeroCarousel slides={slides} label={t("home.upcomingTitle")} prevLabel={t("common.back")} nextLabel={t("common.continue")} />
        </div>
      </section>

      <div className="pp-gutter space-y-12 pt-8">
        {trustItems.length > 0 && (
          <TrustBar items={trustItems} label={t("home.trustLabel")} asOf={t("home.asOf", { date: dateIST(home.trust.as_of, locale, { weekday: undefined, year: "numeric" }) })} />
        )}
        <PromiseStrip items={[
          { key: "sankalp", label: t("home.promiseSankalp") },
          { key: "venue", label: t("home.promiseVenue") },
          { key: "video", label: t("home.promiseVideo", { hours: home.video_sla_hours }) },
          { key: "verified", label: t("home.promiseVerified") },
        ]} />

        <section aria-labelledby="how">
          <SectionTitle id="how">{t("home.howTitle")}</SectionTitle>
          <StepsRow steps={[1, 2, 3, 4].map((n) => ({ title: t(`home.how${n}Title` as "home.how1Title"), text: t(`home.how${n}Text` as "home.how1Text") }))} />
        </section>
        <OrnamentDivider />

        <section aria-labelledby="upcoming">
          <SectionTitle id="upcoming">{t("home.upcomingTitle")}</SectionTitle>
          {home.upcoming.length ? (
            <UpcomingTabs items={home.upcoming} tags={home.tags} labels={{ all: t("common.all"), deity: t("home.tabDeity"),
              dosha: t("home.tabDosha"), benefit: t("home.tabBenefit"), tag: tagLabels }} />
          ) : <p className="text-ink-600">{t("home.emptyUpcoming")}</p>}
          <div className="mt-6 text-center"><Link href="/pujas" className="pp-btn pp-btn-secondary">{t("common.viewAll")}</Link></div>
        </section>
        <OrnamentDivider />

        {home.sevas.length > 0 && (
          <section aria-labelledby="sevas">
            <SectionTitle id="sevas">{t("home.sevasTitle")}</SectionTitle>
            <p className="-mt-3 mb-5 text-ink-600">{t("home.sevasText")}</p>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {home.sevas.slice(0, 3).map((p) => <li key={p.id}><PujaCardItem p={p} featured /></li>)}
            </ul>
          </section>
        )}

        {home.temples.length > 0 && (
          <section aria-labelledby="temples">
            <SectionTitle id="temples">{t("home.templesTitle")}</SectionTitle>
            <ul className="pp-scroll-x -mx-4 flex gap-4 px-4 pb-2">
              {home.temples.map((tp) => (
                <li key={tp.id}><TempleCard href={`/temples/${tp.id}-${tp.slug}`} image={tp.photo} name={tp.name}
                  city={tp.city} venue={t(`venue.${tp.venue_type}` as "venue.temple")} /></li>
              ))}
            </ul>
          </section>
        )}

        {home.gallery.length > 0 && (
          <section aria-labelledby="gallery">
            <SectionTitle id="gallery">{t("home.galleryTitle")}</SectionTitle>
            <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {home.gallery.map((g) => (
                <li key={g.url}><figure className="pp-card overflow-hidden">
                  <img src={g.url} alt={g.alt} loading="lazy" className="aspect-square w-full object-cover" />
                  <figcaption className="p-2 text-small text-ink-600">{g.temple} · {dateIST(g.taken_on, locale, { year: "numeric" })}</figcaption>
                </figure></li>
              ))}
            </ul>
          </section>
        )}

        {home.testimonials.length > 0 && (
          <section aria-labelledby="reviews">
            <SectionTitle id="reviews">{t("home.testimonialsTitle")}</SectionTitle>
            <ul className="grid gap-4 md:grid-cols-3">
              {home.testimonials.map((r, i) => (
                <li key={i}><ReviewCard rating={r.rating} text={r.text} name={r.first_name}
                  meta={[r.city, r.puja].filter(Boolean).join(" · ")} ratingLabel={`${r.rating} / 5`} /></li>
              ))}
            </ul>
          </section>
        )}

        {faqs.length > 0 && (
          <section aria-labelledby="faq">
            <SectionTitle id="faq">{t("home.faqTitle")}</SectionTitle>
            <Accordion items={faqs} />
          </section>
        )}

        <section className="pp-marble pp-card border border-gold-600 px-6 py-8 text-center">
          <h2 className="text-h2">{t("home.ctaTitle")}</h2>
          <p className="mx-auto mt-2 max-w-xl text-ink-600">{t("home.ctaText")}</p>
          <div className="mt-5 flex flex-col justify-center gap-3 sm:flex-row">
            <WhatsAppButton e164={config.whatsapp_number_e164} text={t("puja.whatsappPrefill", { title: config.brand })}
              label={t("home.ctaButton")} />
            <Link href="/pujas" className="pp-btn pp-btn-primary">{t("common.viewAll")}</Link>
          </div>
        </section>
      </div>
    </>
  );
}
