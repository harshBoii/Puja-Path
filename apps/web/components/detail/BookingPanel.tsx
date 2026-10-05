"use client";
import { PackageSelector, QtyStepper, StickyBookBar, cx } from "@pujapath/ui";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { localeHref } from "@/components/Link";
import { capture } from "@/lib/analytics";
import { ApiError, api } from "@/lib/client";
import { money } from "@/lib/format";
import { useBrowserValue } from "@/lib/hooks";
import type { PujaDetail } from "@/lib/types";

function cookieCurrency(): "INR" | "USD" {
  return /(?:^|; )pp_currency=USD/.test(document.cookie) ? "USD" : "INR";
}

function persistCurrency(c: "INR" | "USD") {
  document.cookie = `pp_currency=${c}; path=/; max-age=31536000; samesite=lax`;
  document.documentElement.dataset.currency = c;
}

/** Package radio cards, seva payment choice, chadhava offerings and the Book buttons + mobile sticky bar. */
export default function BookingPanel({ puja, contact }: { puja: PujaDetail; contact: React.ReactNode }) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const cookieCur = useBrowserValue(cookieCurrency, "INR");
  const [chosen, setChosen] = useState<"INR" | "USD" | null>(null);
  const currency = chosen ?? cookieCur;
  const [pkgId, setPkgId] = useState<number | null>(puja.packages[0]?.id ?? null);
  const [mode, setMode] = useState<"full" | "autopay">("full");
  const [qty, setQty] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => capture("puja_detail_viewed", { puja_id: puja.id, kind: puja.kind }), [puja.id, puja.kind]);
  const pkg = puja.packages.find((p) => p.id === pkgId);
  const isChadhava = puja.kind === "chadhava";
  const seva = puja.seva;
  const fmt = (minor: number | null | undefined) => money(minor ?? 0, currency, locale);
  const addonTotal = useMemo(() => puja.addons.reduce((s, a) => s + (qty[a.id] ?? 0) * (a.prices[currency] ?? 0), 0),
    [puja.addons, qty, currency]);
  const perOccurrence = (pkg?.prices[currency] ?? 0) + (isChadhava ? addonTotal : 0);
  const bookable = !!puja.event && (!seva || seva.bookable);
  const autopayAllowed = !!seva?.autopay_allowed && currency === "INR";
  const cta = seva ? t("puja.bookSeva") : isChadhava ? t("puja.chooseOfferings") : t("puja.bookThis");

  const switchCurrency = (c: "INR" | "USD") => {
    persistCurrency(c);
    setChosen(c);
    if (c === "USD") setMode("full");
  };

  const book = async () => {
    if (!pkg || !puja.event) return;
    setBusy(true);
    setError(null);
    try {
      const { id } = await api<{ id: string }>("/drafts", {
        method: "POST", json: { puja_id: puja.id, event_id: puja.event.id, package_id: pkg.id, locale, currency },
      });
      capture("checkout_started", { puja_id: puja.id, package: pkg.code, currency, mode });
      const addons = Object.entries(qty).filter(([, n]) => n > 0).map(([aid, n]) => ({ id: Number(aid), qty: n }));
      if (addons.length) await api(`/drafts/${id}`, { method: "PUT", json: { addons } });
      router.push(localeHref(locale, `/checkout/${id}${seva && mode === "autopay" ? "?mode=autopay" : ""}`));
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "generic";
      setError(t.has(`errors.${code}`) ? t(`errors.${code}` as "errors.generic") : t("errors.generic"));
      setBusy(false);
    }
  };

  const total = seva && mode === "full" ? perOccurrence * seva.occurrences : perOccurrence;
  const button = (
    <button type="button" className="pp-btn pp-btn-primary" onClick={book} disabled={!bookable || busy || !pkg} aria-busy={busy || undefined}>
      {cta}
    </button>
  );

  return (
    <div className="space-y-5 @container">
      <div className="flex items-center gap-2 text-small" role="group" aria-label={t("common.currency")}>
        <span className="text-ink-600">{t("common.currency")}:</span>
        {(["INR", "USD"] as const).map((c) => (
          <button key={c} type="button" className="pp-chip min-h-10" aria-pressed={currency === c} onClick={() => switchCurrency(c)}>{c}</button>
        ))}
      </div>

      <PackageSelector legend={t("puja.packageTitle")} value={pkgId} onChange={setPkgId}
        options={puja.packages.map((p) => ({ id: p.id, label: p.label, namesLabel: t("puja.names", { count: p.max_names }),
          priceLabel: fmt(p.prices[currency]) }))} />

      {isChadhava && puja.addons.length > 0 && (
        <fieldset className="@container">
          <legend className="mb-3 text-h3">{t("puja.chadhavaTitle")}</legend>
          {/* columns follow the panel's own width (narrow sticky column on desktop), not the screen */}
          <ul className="grid gap-3 @xl:grid-cols-2">
            {puja.addons.map((a) => (
              <li key={a.id} className="pp-card flex flex-wrap items-center gap-3 p-3">
                {a.image && <img src={a.image.url} alt="" className="h-14 w-14 shrink-0 rounded-btn object-cover" loading="lazy" />}
                <div className="min-w-32 flex-1">
                  <p className="font-semibold">{a.name}</p>
                  <p className="text-small text-ink-600">{fmt(a.prices[currency])}</p>
                </div>
                <QtyStepper value={qty[a.id] ?? 0} max={a.max_qty} onChange={(n) => setQty((q) => ({ ...q, [a.id]: n }))}
                  label={a.name} decLabel={`${t("common.remove")} ${a.name}`} incLabel={`${t("common.add")} ${a.name}`} />
              </li>
            ))}
          </ul>
        </fieldset>
      )}

      {seva && (
        <fieldset>
          <legend className="mb-3 text-h3">{t("checkout.paymentMode")}</legend>
          <div className="grid gap-3">
            {[
              { v: "full" as const, label: t("puja.payFull", { amount: fmt(perOccurrence * seva.occurrences) }),
                note: t("puja.totalFor", { count: seva.occurrences, amount: fmt(perOccurrence * seva.occurrences) }) },
              ...(autopayAllowed ? [{ v: "autopay" as const, label: t("puja.payAutopay", { amount: fmt(perOccurrence) }),
                note: t("puja.totalFor", { count: seva.occurrences, amount: fmt(perOccurrence * seva.occurrences) }) }] : []),
            ].map((o) => (
              <label key={o.v} className={cx("flex min-h-12 cursor-pointer items-start gap-3 rounded-card p-4",
                mode === o.v ? "pp-foil-border" : "border border-gold-line bg-surface")}>
                <input type="radio" name="paymode" className="mt-1.5 h-5 w-5 accent-[var(--gold-600)]" checked={mode === o.v}
                  onChange={() => setMode(o.v)} />
                <span><span className="block font-semibold">{o.label}</span><span className="text-small text-ink-600">{o.note}</span></span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {!bookable && <p className="rounded-btn bg-gold-100 p-3">{seva ? t("puja.datesUnavailable") : t("puja.notBookable")}</p>}
      {error && <p role="alert" className="text-sindoor-600">{error}</p>}

      <div className="hidden flex-wrap gap-3 md:flex">
        {button}
      </div>
      <div className="flex flex-col gap-3 @xl:flex-row">{contact}</div>

      <StickyBookBar title={pkg ? `${pkg.label} · ${t("puja.names", { count: pkg.max_names })}` : puja.title}
        price={fmt(total)} action={button} />
    </div>
  );
}
