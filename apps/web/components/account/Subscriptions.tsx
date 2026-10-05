"use client";
import { EmptyState, StatusChip } from "@pujapath/ui";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import Link from "@/components/Link";
import { api } from "@/lib/client";
import { dateIST, money } from "@/lib/format";
import AccountGate from "./AccountGate";

type Sub = { id: string; status: string; payment_mode: "full" | "autopay"; mandate_status: string | null; next_occurrence_at: string | null;
  title: string; per_occurrence_minor: number; currency: string; occurrences: { booking_id: string; code: string; status: string; starts_at: string }[] };

export default function Subscriptions() {
  return <div className="pp-gutter pt-6"><AccountGate>{() => <Inner />}</AccountGate></div>;
}

/** Cancelling remaining dates is one screen and one confirmation — as easy as signing up (PRD §8, §12). */
function Inner() {
  const t = useTranslations();
  const locale = useLocale();
  const [subs, setSubs] = useState<Sub[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => api<Sub[]>("/account/subscriptions").then(setSubs).catch(() => setSubs([])), []);
  useEffect(() => { load(); }, [load]);
  if (!subs) return <p aria-busy="true">{t("common.loading")}</p>;
  return (
    <div className="space-y-6">
      <h1 className="text-h1">{t("account.subscriptions")}</h1>
      {msg && <p role="status" className="rounded-btn bg-gold-100 p-3">{msg}</p>}
      {subs.length === 0 ? <EmptyState title={t("account.subscriptionsEmpty")} action={<Link href="/sevas" className="pp-btn pp-btn-primary">{t("nav.sevas")}</Link>} /> : (
        <ul className="space-y-4">
          {subs.map((s) => (
            <li key={s.id} className="pp-card space-y-3 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-h3">{s.title}</h2>
                <StatusChip status={s.status === "active" ? "confirmed" : "cancelled"} label={t(`status.${s.status === "active" ? "active" : "cancelled"}` as "status.active")} />
              </div>
              <p className="text-ink-600">
                {s.payment_mode === "autopay" ? t("account.paymentModeAutopay") : t("account.paymentModeFull")} · {money(s.per_occurrence_minor, s.currency, locale)}
                {s.mandate_status && <> · {t("account.mandate", { status: t(`account.mandateStatus_${s.mandate_status}` as "account.mandateStatus_active") })}</>}
              </p>
              {s.next_occurrence_at && s.status === "active" && <p className="font-semibold">{t("account.nextDate", { date: dateIST(s.next_occurrence_at, locale) })}</p>}
              <ol className="grid gap-1 sm:grid-cols-2">
                {s.occurrences.map((o) => (
                  <li key={o.booking_id} className="flex items-center justify-between gap-2 text-small">
                    <Link href={`/account/bookings/${o.booking_id}`}>{dateIST(o.starts_at, locale)}</Link>
                    <span className="text-ink-600">{t(`status.${o.status}` as "status.confirmed")}</span>
                  </li>
                ))}
              </ol>
              {s.status === "active" && (
                <button type="button" className="pp-btn border border-sindoor-600 text-sindoor-600" onClick={async () => {
                  if (!window.confirm(t("account.cancelRemainingConfirm"))) return;
                  await api(`/account/subscriptions/${s.id}/cancel`, { method: "POST" });
                  setMsg(t("account.cancelRemainingDone"));
                  load();
                }}>{t("account.cancelRemaining")}</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
