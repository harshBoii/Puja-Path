"use client";
import { BottomSheet, IconPhone } from "@pujapath/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { PhoneLink } from "@/components/Contact";
import { api } from "@/lib/client";
import { useBrowserValue } from "@/lib/hooks";
import type { SiteConfig } from "@/lib/types";

function withinHours(h: SiteConfig["support_hours"]): boolean {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: h.tz, weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(new Date());
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(get("weekday"));
  const now = `${get("hour")}:${get("minute")}`;
  return h.days.includes(day) && now >= h.start && now < h.end;
}

/** "Call to book" only within staffed hours from config; outside them it becomes a callback request. */
export default function CallToBook({ config, pujaId, locale, hoursText }: {
  config: SiteConfig; pujaId: number; locale: string; hoursText: string;
}) {
  const t = useTranslations();
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState(false);
  const [sending, setSending] = useState(false);
  const staffed = useBrowserValue<boolean | null>(() => withinHours(config.support_hours), null);
  if (staffed === null) return null;
  if (staffed) {
    return (
      <PhoneLink e164={config.support_phone_e164} className="pp-btn pp-btn-secondary">
        <IconPhone size={20} /><span>{t("puja.callToBook")}</span>
      </PhoneLink>
    );
  }
  return (
    <>
      <button type="button" className="pp-btn pp-btn-secondary" onClick={() => setOpen(true)} aria-haspopup="dialog">
        <IconPhone size={20} /><span>{t("puja.callbackTitle")}</span>
      </button>
      <BottomSheet open={open} onClose={() => setOpen(false)} title={t("puja.callbackTitle")} closeLabel={t("common.close")}>
        {done ? <p role="status">{t("puja.callbackDone")}</p> : (
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            const raw = String(fd.get("phone") ?? "").replace(/[^\d+]/g, "");
            const phone = raw.startsWith("+") ? raw : `+91${raw}`;
            setSending(true);
            try {
              await api("/callback-requests", { method: "POST", json: { phone_e164: phone, name: fd.get("name") || null, puja_id: pujaId, locale } });
              setDone(true);
            } catch { setErr(true); } finally { setSending(false); }
          }}>
            <p className="text-ink-600">{t("puja.callbackText", { hours: hoursText })}</p>
            <label className="block"><span className="mb-1 block font-medium">{t("puja.callbackName")}</span>
              <input name="name" className="pp-input" autoComplete="name" /></label>
            <label className="block"><span className="mb-1 block font-medium">{t("puja.callbackPhone")}</span>
              <input name="phone" className="pp-input" inputMode="tel" autoComplete="tel" required /></label>
            {err && <p role="alert" className="text-sindoor-600">{t("common.error")}</p>}
            <button className="pp-btn pp-btn-primary w-full" aria-busy={sending || undefined}>{t("puja.callbackSubmit")}</button>
          </form>
        )}
      </BottomSheet>
    </>
  );
}
