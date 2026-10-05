import {
  Accordion,
  BenefitList,
  DeliverablesList,
  FactBox,
  IconMapPin,
  OccasionChip,
  PromiseStrip,
  ReviewCard,
  RitualSteps,
  SectionNav,
  SectionTitle,
  VenueBadge,
} from "@pujapath/ui";
import { getLocale, getTranslations } from "next-intl/server";

import { WhatsAppButton } from "@/components/Contact";
import JsonLd from "@/components/JsonLd";
import Link from "@/components/Link";
import LocalTime from "@/components/LocalTime";
import Price from "@/components/Price";
import PujaCardItem from "@/components/PujaCardItem";
import WishlistButton from "@/components/WishlistButton";
import { getConfig } from "@/lib/api";
import { dateIST, pujaPath, renderTokens, supportDays, timeIST } from "@/lib/format";
import { SITE, breadcrumbs, faqPage } from "@/lib/seo";
import { Paragraphs } from "@/lib/text";
import type { PujaDetail } from "@/lib/types";
import BookingCountdown from "./BookingCountdown";
import BookingPanel from "./BookingPanel";
import CallToBook from "./CallToBook";
import Collapsible from "./Collapsible";
import ShareButton from "./ShareButton";

export default async function PujaDetailView({ puja }: { puja: PujaDetail }) {
  const [t, locale, config] = await Promise.all([getTranslations(), getLocale(), getConfig()]);
  const ev = puja.event;
  const temple = puja.temple_detail;
  const venue = t(`venue.${temple.venue_type}` as "venue.temple");
  const supportHours = `${supportDays(config.support_hours.days, locale)} ${config.support_hours.start}–${config.support_hours.end} IST`;
  const tokens = {
    video_sla_hours: puja.video_sla_hours, booking_cutoff_hours: config.booking_cutoff_hours_default,
    refund_days: config.refund_expected_days, gotra_fallback: config.gotra_fallback[locale] ?? config.gotra_fallback.en,
    support_hours: supportHours,
  };
  const faqs = [...puja.faqs, ...puja.global_faqs.map((f) => ({ q: f.q, a: renderTokens(f.a, tokens) }))];
  const sections = [
    { id: "about", label: t("puja.sectionAbout") },
    { id: "benefits", label: t("puja.sectionBenefits") },
    { id: "rituals", label: t("puja.sectionRituals") },
    { id: "temple", label: t("puja.sectionTemple") },
    { id: "receive", label: t("puja.sectionReceive") },
    { id: "reviews", label: t("puja.sectionReviews") },
    ...(faqs.length ? [{ id: "faq", label: t("puja.sectionFaq") }] : []),
  ];
  const deliverables = [...puja.deliverables, ...(puja.prasad_box ? ["prasad"] : [])]
    .map((d) => t(`puja.receive_${d}` as "puja.receive_photos"));
  const url = `${SITE}/${locale}${pujaPath(puja)}`;
  const minPrice = Math.min(...puja.packages.map((p) => p.prices.INR ?? Infinity));
  const listPath = puja.kind === "seva" ? "/sevas" : "/pujas";

  const freqLabel = puja.seva ? (puja.seva.rrule.includes("DAILY") ? t("puja.freqDaily")
    : puja.seva.rrule.includes("MONTHLY") ? t("puja.freqMonthly") : t("puja.freqWeekly")) : "";

  return (
    <article className="pp-gutter pt-4">
      <JsonLd data={[
        breadcrumbs([{ name: t("nav.home"), url: `/${locale}` },
          { name: puja.kind === "seva" ? t("nav.sevas") : t("nav.pujas"), url: `/${locale}${listPath}` },
          { name: puja.title, url: `/${locale}${pujaPath(puja)}` }]),
        ...(ev ? [{
          "@context": "https://schema.org", "@type": "Event", name: puja.title, description: puja.meta_description,
          startDate: ev.starts_at, eventStatus: "https://schema.org/EventScheduled",
          eventAttendanceMode: "https://schema.org/OnlineEventAttendanceMode", image: puja.images.map((i) => i?.url),
          location: { "@type": "Place", name: temple.name,
            address: { "@type": "PostalAddress", streetAddress: temple.address, addressLocality: temple.city,
              addressRegion: temple.state, addressCountry: "IN" } },
          organizer: { "@type": "Organization", name: config.brand, url: SITE },
          offers: { "@type": "Offer", price: (minPrice / 100).toFixed(0), priceCurrency: "INR", url,
            availability: "https://schema.org/InStock", validThrough: ev.booking_cutoff_at },
        }] : []),
        ...(faqs.length ? [faqPage(faqs)] : []),
      ]} />

      {/* 1. gallery */}
      <div className="pp-scroll-x -mx-4 flex gap-3 px-4" aria-label={puja.title}>
        {puja.images.filter(Boolean).slice(0, 6).map((img, i) => (
          <img key={i} src={img!.url} srcSet={img!.srcset} alt={img!.alt} sizes="(min-width: 768px) 600px, 90vw"
            className="aspect-[4/3] w-[88%] shrink-0 snap-center rounded-card object-cover md:w-[48%]"
            loading={i === 0 ? "eager" : "lazy"} fetchPriority={i === 0 ? "high" : undefined} />
        ))}
      </div>

      {/* One BookingPanel (one hydration): after the title block on mobile, a sticky column on desktop. */}
      <div className="mt-6 grid gap-x-8 lg:grid-cols-[1fr_420px]">
        <div className="min-w-0 space-y-10 lg:col-start-1 lg:row-start-1">
          {/* 2. title block */}
          <header className="space-y-2">
            <div className="flex items-start justify-between gap-3">
              {puja.occasion_chip ? <OccasionChip>{puja.occasion_chip}</OccasionChip> : <span />}
              <div className="flex gap-2">
                <ShareButton title={puja.title} label={t("common.share")} text={t("puja.sharePrefill", { title: puja.title, url: "{url}" })} />
                <WishlistButton pujaId={puja.id} labels={{ add: t("common.wishlistAdd"), remove: t("common.wishlistRemove") }} />
              </div>
            </div>
            <h1 className="pp-foil-text text-display">{puja.title}</h1>
            {puja.subtitle && <p className="text-h3 font-normal text-ink-600">{puja.subtitle}</p>}
            <p className="flex flex-wrap items-center gap-2">
              <IconMapPin size={20} className="text-gold-700" />
              <Link href={`/temples/${temple.id}-${temple.slug}`} className="pp-link">{temple.name}</Link>
              <span className="text-ink-600">{temple.city}</span>
              <VenueBadge label={venue} />
            </p>
            {ev && (
              <p className="font-semibold">
                {dateIST(ev.starts_at, locale, { year: "numeric" })} · {timeIST(ev.starts_at, locale)} {t("common.ist")}
                <LocalTime iso={ev.starts_at} locale={locale} template={t("common.yourTime", { time: "{time}" })} />
              </p>
            )}
            {/* 3. countdown: real cutoff, under 72 hours only */}
            {ev && <BookingCountdown eventId={ev.id} />}
          </header>

          {/* schedule (sevas) */}
          {puja.seva && (
            <section aria-labelledby="schedule" className="pp-card p-5">
              <h2 id="schedule" className="text-h3">{t("puja.scheduleTitle")}</h2>
              <p className="mt-1">{t("puja.scheduleSummary", { freq: freqLabel, count: puja.seva.occurrences })}</p>
              {puja.seva.dates.length > 0 ? (
                <>
                  <p className="mt-2 text-ink-600">{t("puja.firstDate")}: {dateIST(puja.seva.dates[0].starts_at, locale, { year: "numeric" })}</p>
                  <p className="mt-3 font-semibold">{t("puja.allDates")}</p>
                  <ol className="mt-1 grid gap-1 sm:grid-cols-2">
                    {puja.seva.dates.map((d, i) => (
                      <li key={d.id} className="text-small">{i + 1}. {dateIST(d.starts_at, locale)} · {timeIST(d.starts_at, locale)} {t("common.ist")}</li>
                    ))}
                  </ol>
                </>
              ) : <p className="mt-2 text-ink-600">{t("puja.datesUnavailable")}</p>}
            </section>
          )}

        </div>

        {/* 4-5. packages + book */}
        <aside className="mt-10 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:mt-0">
          <div className="lg:sticky lg:top-24 lg:rounded-card lg:border lg:border-gold-600 lg:bg-surface lg:p-5 lg:shadow-card">
            <BookingPanel puja={puja} contact={<Contact />} />
          </div>
        </aside>

        <div className="mt-10 min-w-0 space-y-10 lg:col-start-1 lg:row-start-2">
          {/* 6. promise strip, using this puja's SLA */}
          <PromiseStrip items={[
            { key: "sankalp", label: t("home.promiseSankalp") },
            { key: "venue", label: t("home.promiseVenue") },
            { key: "video", label: t("home.promiseVideo", { hours: puja.video_sla_hours }) },
            { key: "verified", label: t("home.promiseVerified") },
          ]} />

          {/* 7. sticky section nav */}
          <SectionNav sections={sections} label={puja.title} />

          {/* 8-9. about + facts */}
          <section id="about" aria-labelledby="about-h" className="scroll-mt-32 space-y-4">
            <SectionTitle id="about-h">{t("puja.sectionAbout")}</SectionTitle>
            <Collapsible more={t("common.readMore")} less={t("common.readLess")}><Paragraphs text={puja.about_md} /></Collapsible>
            <FactBox facts={[
              { label: t("puja.factTradition"), value: puja.facts.tradition },
              { label: t("puja.factDuration"), value: t("common.minutes", { count: puja.facts.duration_minutes }) },
              { label: t("puja.factPriests"), value: String(puja.facts.priests_count) },
              { label: t("puja.factLanguage"), value: puja.facts.sankalp_language },
            ]} />
          </section>

          {/* 10. benefits */}
          <section id="benefits" aria-labelledby="benefits-h" className="scroll-mt-32">
            <SectionTitle id="benefits-h">{t("puja.sectionBenefits")}</SectionTitle>
            <BenefitList items={puja.benefits} />
          </section>

          {/* 11. rituals */}
          <section id="rituals" aria-labelledby="rituals-h" className="scroll-mt-32">
            <SectionTitle id="rituals-h">{t("puja.sectionRituals")}</SectionTitle>
            <RitualSteps items={puja.rituals} mainLabel={t("puja.mainRitual")} />
          </section>

          {/* 12. temple */}
          <section id="temple" aria-labelledby="temple-h" className="scroll-mt-32">
            <SectionTitle id="temple-h">{t("puja.sectionTemple")}</SectionTitle>
            <div className="pp-card grid gap-4 overflow-hidden md:grid-cols-[240px_1fr]">
              {temple.photos[0] && <img src={temple.photos[0].url} alt={temple.photos[0].alt} loading="lazy" className="h-full w-full object-cover" />}
              <div className="space-y-2 p-5">
                <h3 className="text-h3"><Link href={`/temples/${temple.id}-${temple.slug}`} className="text-ink-900">{temple.name}</Link></h3>
                <p className="text-small text-ink-600">{locale === "en" && <>{t("puja.presidingDeity")}: {temple.presiding_deity} · </>}{temple.city}, {temple.state} · <VenueBadge label={venue} /></p>
                <Paragraphs text={temple.history_md} className="text-ink-600" />
                {temple.lat && temple.lng && (
                  <a className="pp-link inline-flex min-h-12 items-center" target="_blank" rel="noopener noreferrer"
                    href={`https://www.google.com/maps/search/?api=1&query=${temple.lat},${temple.lng}`}>{t("puja.mapLink")}</a>
                )}
              </div>
            </div>
          </section>

          {/* 13. you will receive (same SLA number as the badge) */}
          <section id="receive" aria-labelledby="receive-h" className="scroll-mt-32">
            <SectionTitle id="receive-h">{t("puja.sectionReceive")}</SectionTitle>
            <DeliverablesList items={deliverables} note={t("puja.receiveWithin", { hours: puja.video_sla_hours })} />
            {puja.prasad_box && (
              <p className="mt-3 text-small text-ink-600">{t("puja.prasadBox")}: {puja.prasad_box.map((i) => t(`puja.prasad_${i}` as "puja.prasad_kumkum")).join(", ")}</p>
            )}
          </section>

          {/* 14. chadhava preview */}
          {puja.kind !== "chadhava" && puja.addons.length > 0 && (
            <section aria-labelledby="addons-h">
              <SectionTitle id="addons-h">{t("puja.chadhavaTitle")}</SectionTitle>
              <ul className="grid gap-3 sm:grid-cols-2">
                {puja.addons.map((a) => (
                  <li key={a.id} className="pp-card flex items-center gap-3 p-3">
                    {a.image && <img src={a.image.url} alt="" className="h-14 w-14 rounded-btn object-cover" loading="lazy" />}
                    <span className="flex-1 font-medium">{a.name}</span>
                    <span className="font-semibold"><Price prices={a.prices} /></span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 15. reviews */}
          <section id="reviews" aria-labelledby="reviews-h" className="scroll-mt-32">
            <SectionTitle id="reviews-h">{t("puja.sectionReviews")}</SectionTitle>
            {puja.reviews.length ? (
              <ul className="grid gap-4 md:grid-cols-2">
                {puja.reviews.map((r, i) => (
                  <li key={i}><ReviewCard rating={r.rating} text={r.text} name={r.first_name} ratingLabel={`${r.rating} / 5`}
                    meta={[r.city, r.puja].filter(Boolean).join(" · ")} /></li>
                ))}
              </ul>
            ) : <p className="text-ink-600">{t("puja.reviewsEmpty")}</p>}
          </section>

          {/* 16. FAQ: puja-specific then global */}
          {faqs.length > 0 && (
            <section id="faq" aria-labelledby="faq-h" className="scroll-mt-32">
              <SectionTitle id="faq-h">{t("puja.sectionFaq")}</SectionTitle>
              <Accordion items={faqs} />
            </section>
          )}
        </div>
      </div>

      {/* 17. recommendations */}
      {puja.recommendations.length > 0 && (
        <section aria-labelledby="recs-h" className="mt-12">
          <SectionTitle id="recs-h">{t("puja.recsTitle")}</SectionTitle>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {puja.recommendations.map((p) => <li key={p.id}><PujaCardItem p={p} /></li>)}
          </ul>
        </section>
      )}

      {/* 18. help box */}
      <section className="pp-marble pp-card mt-12 border border-gold-600 p-6 text-center">
        <h2 className="text-h2">{t("puja.helpTitle")}</h2>
        <p className="mt-1 text-ink-600">{t("puja.helpText")}</p>
        <div className="mt-4 flex justify-center">
          <WhatsAppButton e164={config.whatsapp_number_e164} text={t("puja.whatsappPrefill", { title: puja.title })} label={t("puja.bookWhatsapp")} />
        </div>
      </section>
    </article>
  );

  function Contact() {
    return (
      <>
        <WhatsAppButton e164={config.whatsapp_number_e164} text={t("puja.whatsappPrefill", { title: puja.title })}
          label={t("puja.bookWhatsapp")} />
        <CallToBook config={config} pujaId={puja.id} locale={locale} hoursText={supportHours} />
      </>
    );
  }
}
