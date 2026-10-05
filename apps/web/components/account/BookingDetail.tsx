"use client";
import { BookingTimeline, IconDownload, StatusChip } from "@pujapath/ui";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { WhatsAppButton } from "@/components/Contact";
import Link from "@/components/Link";
import ProofPlayer from "@/components/ProofPlayer";
import { api } from "@/lib/client";
import { dateIST, money, timeIST } from "@/lib/format";
import AccountGate from "./AccountGate";

type Detail = {
  id: string; code: string; status: string; currency: string; total_minor: number; puja_id: number; slug: string; kind: string;
  title: string; temple: string; starts_at: string; package: string; booking_cutoff_at: string; video_sla_hours: number;
  names: { name: string; relation: string | null; gotra: string | null; gotra_unknown: boolean; nakshatra: string | null }[];
  can_cancel: boolean; timeline: { key: string; done: boolean; at: string | null }[];
  proof: { clip: { url: string; poster: string } | null; full_video: { type: "mp4" | "hls"; url: string } | null;
    photos: { url: string; alt: string }[]; share_path: string } | null;
  shipment: { status: string; courier: string | null; awb: string | null; tracking_url: string | null } | null;
  has_invoice: boolean;
};

export default function BookingDetail({ id, whatsapp }: { id: string; whatsapp: string }) {
  return <div className="pp-gutter pt-6"><AccountGate>{() => <Inner id={id} whatsapp={whatsapp} />}</AccountGate></div>;
}

function Inner({ id, whatsapp }: { id: string; whatsapp: string }) {
  const t = useTranslations();
  const locale = useLocale();
  const [b, setB] = useState<Detail | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => api<Detail>(`/account/bookings/${id}`).then(setB).catch(() => setMsg(t("common.error"))), [id, t]);
  useEffect(() => { load(); }, [load]);
  if (!b) return <p aria-busy="true">{msg ?? t("common.loading")}</p>;
  const amount = money(b.total_minor, b.currency, locale);
  const cancel = async () => {
    if (!window.confirm(t("account.cancelConfirm", { amount }))) return;
    await api(`/account/bookings/${id}/cancel`, { method: "POST" });
    setMsg(t("account.cancelDone"));
    load();
  };
  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <StatusChip status={b.status} label={t(`status.${b.status}` as "status.confirmed")} />
        <h1 className="text-h1">{b.title}</h1>
        <p className="text-ink-600">{b.temple} · {dateIST(b.starts_at, locale, { year: "numeric" })} · {timeIST(b.starts_at, locale)} {t("common.ist")}</p>
        <p className="font-semibold">{t("account.bookingCode", { code: b.code })} · {b.package} · {amount}</p>
      </header>
      {msg && <p role="status" className="rounded-btn bg-gold-100 p-3">{msg}</p>}

      {b.proof && (
        <section aria-labelledby="pr" className="space-y-4">
          <h2 id="pr" className="text-h2">{t("account.proofTitle")}</h2>
          {b.proof.clip && <div><p className="mb-2 font-semibold">{t("account.sankalpClip")}</p>
            <ProofPlayer src={b.proof.clip.url} poster={b.proof.clip.poster} type="mp4" label={t("account.sankalpClip")} /></div>}
          {b.proof.full_video && <div><p className="mb-2 font-semibold">{t("account.fullVideo")}</p>
            <ProofPlayer src={b.proof.full_video.url} type={b.proof.full_video.type} label={t("account.fullVideo")} /></div>}
          {b.proof.photos.length > 0 && (
            <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">{b.proof.photos.map((p) => (
              <li key={p.url}><img src={p.url} alt={p.alt} loading="lazy" className="aspect-square w-full rounded-card object-cover" /></li>))}</ul>
          )}
          <Link href={`/${b.proof.share_path.split("/").slice(1).join("/")}`} locale={b.proof.share_path.split("/")[0]}
            className="pp-btn pp-btn-secondary">{t("account.shareProof")}</Link>
        </section>
      )}

      <section aria-labelledby="tl" className="pp-card p-5">
        <h2 id="tl" className="mb-4 text-h3">{t("account.timeline")}</h2>
        <BookingTimeline steps={b.timeline.map((s) => ({ key: s.key, label: t(`timeline.${s.key}` as "timeline.paid"), done: s.done,
          at: s.at && s.done ? dateIST(s.at, locale) : null }))} />
      </section>

      {b.shipment && (
        <section className="pp-card p-5">
          <h2 className="text-h3">{t("account.shipment")}</h2>
          <p className="mt-1">{[b.shipment.courier, b.shipment.awb].filter(Boolean).join(" · ")}</p>
          {b.shipment.tracking_url && <a href={b.shipment.tracking_url} target="_blank" rel="noopener noreferrer" className="pp-link">{t("account.track")}</a>}
        </section>
      )}

      <section className="pp-card p-5">
        <h2 className="mb-2 text-h3">{t("account.names")}</h2>
        <ul className="space-y-1">{b.names.map((n, i) => (
          <li key={i}><strong>{n.name}</strong> <span className="text-ink-600">{[n.relation, n.gotra_unknown ? null : n.gotra, n.nakshatra].filter(Boolean).join(" · ")}</span></li>))}</ul>
      </section>

      <div className="flex flex-col flex-wrap gap-3 sm:flex-row">
        {b.has_invoice && <a href={`/api/v1/account/bookings/${id}/invoice.pdf`} className="pp-btn pp-btn-secondary"><IconDownload size={20} />{t("account.invoice")}</a>}
        <Link href={`/${b.kind === "seva" ? "sevas" : "pujas"}/${b.puja_id}-${b.slug}`} className="pp-btn pp-btn-primary">{t("account.bookAgain")}</Link>
        <WhatsAppButton e164={whatsapp} text={t("account.supportPrefill", { code: b.code })} label={t("account.support")} />
      </div>

      <section className="pp-card p-5">
        {b.can_cancel ? (
          <>
            <p className="mb-3 text-ink-600">{t("account.cancelWindow", { date: `${dateIST(b.booking_cutoff_at, locale)} ${timeIST(b.booking_cutoff_at, locale)} ${t("common.ist")}` })}</p>
            <button type="button" className="pp-btn border border-sindoor-600 text-sindoor-600" onClick={cancel}>{t("account.cancel")}</button>
          </>
        ) : ["confirmed", "locked"].includes(b.status) ? <p className="text-ink-600">{t("account.noCancel")}</p> : null}
      </section>
    </div>
  );
}
