import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import {
  Accordion, ArchFrame, BenefitList, BookingTimeline, BottomSheet, Countdown, DeliverablesList, EmptyState, FactBox, GlyphBell,
  GlyphConch, GlyphDiya, GlyphKalash, GlyphLotus, GlyphTemple, HeroCarousel, OrnamentDivider, PackageSelector, PriceSummary,
  PromiseStrip, PujaCard, QtyStepper, ReviewCard, RitualSteps, SectionNav, Skeleton, StatusChip, StepsRow, StickyBookBar,
  TempleCard, Toast, TrustBar,
} from "../index";
import { tr } from "./i18n";

const meta: Meta = { title: "Components/Storefront" };
export default meta;
type S = StoryObj;
const L = (g: Record<string, unknown>) => (g.locale as string) ?? "en";

export const Glyphs: S = {
  render: () => (
    <div className="flex gap-4 text-gold-700">{[GlyphLotus, GlyphDiya, GlyphKalash, GlyphTemple, GlyphBell, GlyphConch].map((G, i) => <G key={i} size={40} />)}</div>
  ),
};

export const Arch: S = { render: () => <div className="w-64"><ArchFrame src="/images/seed/rudrabhishekam.svg" alt="Trident" /></div> };
export const Divider: S = { render: () => <OrnamentDivider /> };

export const Promise: S = {
  render: (_, { globals }) => (
    <PromiseStrip items={[{ key: "sankalp", label: tr(L(globals), "home.promiseSankalp") }, { key: "venue", label: tr(L(globals), "home.promiseVenue") },
      { key: "video", label: tr(L(globals), "home.promiseVideo", { hours: 48 }) }, { key: "verified", label: tr(L(globals), "home.promiseVerified") }]} />
  ),
};

export const Steps: S = {
  render: (_, { globals }) => <StepsRow steps={[1, 2, 3, 4].map((n) => ({ title: tr(L(globals), `home.how${n}Title`), text: tr(L(globals), `home.how${n}Text`) }))} />,
};

export const Trust: S = {
  render: (_, { globals }) => (
    <TrustBar label={tr(L(globals), "home.trustLabel")} asOf={tr(L(globals), "home.asOf", { date: "5 Oct 2026" })}
      items={[{ key: "p", text: tr(L(globals), "home.pujasCompleted", { count: "1,200" }) }, { key: "d", text: tr(L(globals), "home.devoteesServed", { count: "900" }) }]} />
  ),
};

export const Cards: S = {
  render: (_, { globals }) => (
    <div className="grid gap-4 sm:grid-cols-3">
      <PujaCard href="#" image={{ url: "/images/seed/navagraha.svg", alt: "" }} chip={tr(L(globals), "tags.navagraha")} title={tr(L(globals), "tags.navagraha")}
        temple="Kanchipuram" venue={tr(L(globals), "venue.yagashala")} dateLabel="Tue, 6 Oct · 6:30 am IST" priceLabel={tr(L(globals), "common.from", { price: "₹1,101" })}
        bookLabel={tr(L(globals), "common.book")} />
      <TempleCard href="#" image={{ url: "/images/seed/temple-ghat.svg", alt: "" }} name="Dashashwamedh Ghat" city="Varanasi" venue={tr(L(globals), "venue.ghat")} />
      <ReviewCard rating={5} text="—" name="Lakshmi" meta="Hyderabad" ratingLabel="5 / 5" />
    </div>
  ),
};

export const Packages: S = {
  render: function Render(_, { globals }) {
    const [v, setV] = useState<number | null>(1);
    return <PackageSelector legend={tr(L(globals), "puja.packageTitle")} value={v} onChange={setV}
      options={[["individual", 1, "₹501"], ["couple", 2, "₹851"], ["family", 4, "₹1,251"]].map(([c, n, p], i) => ({
        id: i + 1, label: String(c), namesLabel: `${n}`, priceLabel: String(p) }))} />;
  },
};

export const Details: S = {
  render: (_, { globals }) => (
    <div className="space-y-6">
      <FactBox facts={[{ label: tr(L(globals), "puja.factTradition"), value: "Shaiva Agama" }, { label: tr(L(globals), "puja.factDuration"), value: "90" },
        { label: tr(L(globals), "puja.factPriests"), value: "3" }, { label: tr(L(globals), "puja.factLanguage"), value: "Sanskrit" }]} />
      <BenefitList items={[{ title: tr(L(globals), "puja.sectionBenefits"), line: tr(L(globals), "home.how3Text") }]} />
      <RitualSteps mainLabel={tr(L(globals), "puja.mainRitual")} items={[{ title: "1", text: tr(L(globals), "home.how1Text") }, { title: "2", text: tr(L(globals), "home.how3Text"), main: true }]} />
      <DeliverablesList items={["sankalp_clip", "full_video", "photos"].map((d) => tr(L(globals), `puja.receive_${d}`))} note={tr(L(globals), "puja.receiveWithin", { hours: 48 })} />
      <Accordion items={[{ q: tr(L(globals), "home.faqTitle"), a: tr(L(globals), "home.ctaText") }]} />
    </div>
  ),
};

export const Checkout: S = {
  render: function Render(_, { globals }) {
    const [q, setQ] = useState(1);
    return (
      <div className="space-y-4">
        <QtyStepper value={q} max={5} onChange={setQ} label="Qty" decLabel="-" incLabel="+" />
        <PriceSummary lines={[{ label: tr(L(globals), "checkout.linePackage", { package: "Individual" }), value: "₹601" },
          { label: tr(L(globals), "checkout.lineShipping"), value: "₹99" }]} totalLabel={tr(L(globals), "checkout.total")} total="₹700" note={tr(L(globals), "checkout.totalNote")} />
        <BookingTimeline steps={["paid", "scheduled", "performed", "video_sent"].map((k, i) => ({ key: k, label: tr(L(globals), `timeline.${k}`), done: i < 2 }))} />
        <div className="flex gap-2"><StatusChip status="confirmed" label={tr(L(globals), "status.confirmed")} /><StatusChip status="refunded" label={tr(L(globals), "status.refunded")} /></div>
      </div>
    );
  },
};

export const Feedback: S = {
  render: function Render(_, { globals }) {
    const [open, setOpen] = useState(false);
    const [toast, setToast] = useState<string | null>(null);
    return (
      <div className="space-y-4">
        <EmptyState title={tr(L(globals), "account.bookingsEmpty")} />
        <Skeleton className="h-24" />
        <Countdown deadlineIso={new Date(Date.now() + 5 * 3600e3).toISOString()} initialRemainingMs={5 * 3600e3}
          format={({ h, m, s }) => tr(L(globals), "puja.closesIn", { time: `${h}:${m}:${s}` })} />
        <div className="flex gap-2">
          <button className="pp-btn pp-btn-secondary" onClick={() => setOpen(true)}>{tr(L(globals), "common.filters")}</button>
          <button className="pp-btn pp-btn-secondary" onClick={() => setToast(tr(L(globals), "common.saved"))}>Toast</button>
        </div>
        <BottomSheet open={open} onClose={() => setOpen(false)} title={tr(L(globals), "common.filters")} closeLabel={tr(L(globals), "common.close")}>
          <p>{tr(L(globals), "listing.subtitle")}</p>
        </BottomSheet>
        <Toast message={toast} onDone={() => setToast(null)} />
      </div>
    );
  },
};

export const Navigation: S = {
  render: (_, { globals }) => (
    <div className="h-64 overflow-auto">
      <SectionNav label="sections" sections={["sectionAbout", "sectionBenefits", "sectionRituals"].map((k) => ({ id: k, label: tr(L(globals), `puja.${k}`) }))} />
      <HeroCarousel label="hero" prevLabel="prev" nextLabel="next" slides={["rudrabhishekam", "navagraha"].map((s) => (
        <div key={s} className="w-40"><ArchFrame src={`/images/seed/${s}.svg`} alt="" /></div>))} />
      <StickyBookBar title="Individual · 1" price="₹501" action={<button className="pp-btn pp-btn-primary">{tr(L(globals), "puja.bookThis")}</button>} />
    </div>
  ),
};
