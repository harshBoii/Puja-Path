"use client";
import { useState } from "react";

import { Card, PageTitle, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

const LOCALES = ["en", "hi", "ta", "te"] as const;
type F = { question: string; answer_md: string };

/** Home/FAQ page questions per locale. Use {video_sla_hours}, {booking_cutoff_hours}, {refund_days}, {gotra_fallback} and
 *  {support_hours} instead of typing numbers: they render from site config everywhere. */
export default function Faqs() {
  const [locale, setLocale] = useState<(typeof LOCALES)[number]>("en");
  const { data, setData } = useApi<F[]>(`/admin/faqs/${locale}`);
  const { run, busy, view } = useAction();
  return (
    <>
      <PageTitle>FAQs</PageTitle>
      <p className="-mt-3 mb-4 text-small text-ink-600">Tokens: {"{video_sla_hours} {booking_cutoff_hours} {refund_days} {gotra_fallback} {support_hours}"}. The home page shows the first 8.</p>
      <div className="mb-3 flex gap-2">{LOCALES.map((l) => <button key={l} className="pp-chip" data-selected={l === locale} onClick={() => setLocale(l)}>{l}</button>)}</div>
      {view}
      <Card>
        {(data ?? []).map((f, i) => (
          <div key={i} lang={locale} className="mb-3 grid gap-2 border-b border-marble-100 pb-3">
            <input className="pp-input font-semibold" value={f.question} onChange={(e) => setData((data ?? []).map((x, k) => (k === i ? { ...x, question: e.target.value } : x)))} />
            <textarea className="pp-input" value={f.answer_md} onChange={(e) => setData((data ?? []).map((x, k) => (k === i ? { ...x, answer_md: e.target.value } : x)))} />
            <div className="flex gap-3 text-small">
              <button className="pp-link" disabled={i === 0} onClick={() => { const d = [...(data ?? [])]; [d[i - 1], d[i]] = [d[i], d[i - 1]]; setData(d); }}>Move up</button>
              <button className="pp-link" onClick={() => setData((data ?? []).filter((_, k) => k !== i))}>Remove</button>
            </div>
          </div>
        ))}
        <div className="flex gap-2">
          <button className="pp-btn pp-btn-secondary" onClick={() => setData([...(data ?? []), { question: "", answer_md: "" }])}>Add question</button>
          <button className="pp-btn pp-btn-primary" disabled={busy} onClick={() => run(() => api(`/admin/faqs/${locale}`, { method: "PUT", json: data }), "Saved.")}>Save {locale}</button>
        </div>
      </Card>
    </>
  );
}
