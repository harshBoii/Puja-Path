"use client";
import { BookingTimeline, DiyaLoader, GlyphDiya } from "@pujapath/ui";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import Link from "@/components/Link";
import { capture } from "@/lib/analytics";
import { api } from "@/lib/client";

/** "Confirming your booking" -> polls status until the webhook has confirmed it. */
export default function Success({ id, slaHours }: { id: string; slaHours: number }) {
  const t = useTranslations();
  const [status, setStatus] = useState<{ status: string; code: string; video_sla_hours?: number } | null>(null);
  useEffect(() => {
    let stop = false;
    let n = 0;
    const tick = async () => {
      try {
        const s = await api<{ status: string; code: string; video_sla_hours?: number }>(`/bookings/${id}/status`);
        if (stop) return;
        setStatus(s);
        if (s.status === "pending_payment" && n++ < 60) setTimeout(tick, 2000);
      } catch { if (!stop && n++ < 60) setTimeout(tick, 3000); }
    };
    tick();
    return () => { stop = true; };
  }, [id]);
  const confirmed = status && !["draft", "pending_payment"].includes(status.status);
  useEffect(() => { if (confirmed) capture("booking_confirmed", { booking_id: id }); }, [confirmed, id]);
  if (!confirmed) {
    return (
      <div className="pp-card mx-auto max-w-xl p-8 text-center" role="status" aria-live="polite">
        <h1 className="text-h2">{t("checkout.confirming")}</h1>
        <DiyaLoader label={t("checkout.confirmingText")} className="py-6" />
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="pp-card pp-foil-border p-6 text-center">
        <GlyphDiya size={48} className="mx-auto text-gold-600" />
        <h1 className="mt-2 text-h1">{t("success.title")}</h1>
        <p className="mt-2 text-ink-600">{t("success.code")}</p>
        <p className="font-display text-display tracking-widest">{status.code}</p>
        <p className="mt-2">{t("success.whatsappSent")}</p>
      </div>
      <section className="pp-card p-6">
        <h2 className="mb-4 text-h3">{t("success.nextTitle")}</h2>
        <BookingTimeline steps={[
          { key: "1", label: t("success.next1"), done: false }, { key: "2", label: t("success.next2"), done: false },
          { key: "3", label: t("success.next3", { hours: status.video_sla_hours ?? slaHours }), done: false }, { key: "4", label: t("success.next4"), done: false },
        ]} />
      </section>
      <div className="flex flex-col gap-3 sm:flex-row">
        <a href={`/api/v1/account/bookings/${id}/calendar.ics`} className="pp-btn pp-btn-secondary flex-1">{t("success.calendar")}</a>
        <Link href={`/account/bookings/${id}`} className="pp-btn pp-btn-primary flex-1">{t("success.viewBooking")}</Link>
      </div>
    </div>
  );
}
