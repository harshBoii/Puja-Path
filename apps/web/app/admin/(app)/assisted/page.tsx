"use client";
import { useState } from "react";

import { Card, Field, PageTitle, fmtDate, inr, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

type P = { id: number; title: string; status: string };
type Ev = { id: number; starts_at: string; booking_cutoff_at: string };
type Detail = { packages: { id: number; label: string; max_names: number; prices: { INR: number; USD: number } }[] };
type NameRow = { name: string; gotra: string; gotra_unknown: boolean; nakshatra: string };

/** Journey C: an agent creates the booking for a phone number and sends a payment link on WhatsApp. */
export default function Assisted() {
  const pujas = useApi<P[]>("/admin/pujas");
  const [pujaId, setPujaId] = useState<number | null>(null);
  const events = useApi<Ev[]>(pujaId ? `/admin/events?puja_id=${pujaId}` : null);
  const detail = useApi<Detail>(pujaId ? `/en/pujas/${pujaId}` : null);
  const [names, setNames] = useState<NameRow[]>([{ name: "", gotra: "", gotra_unknown: false, nakshatra: "" }]);
  const [result, setResult] = useState<{ code: string; pay_path: string; total_minor: number } | null>(null);
  const { run, busy, view } = useAction();
  const [now] = useState(() => Date.now());
  const setName = (i: number, patch: Partial<NameRow>) => setNames(names.map((x, k) => (k === i ? { ...x, ...patch } : x)));
  return (
    <>
      <PageTitle>Assisted booking</PageTitle>
      {view}
      {result && <Card title="Payment link sent"><p>Booking <strong>{result.code}</strong> · {inr(result.total_minor)} · link: <code>{result.pay_path}</code></p></Card>}
      <form className="pp-card max-w-2xl space-y-3 p-4" onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        run(async () => setResult(await api("/admin/assisted-bookings", { method: "POST", json: {
          phone_e164: fd.get("phone"), event_id: Number(fd.get("event")), package_id: Number(fd.get("package")),
          locale: fd.get("locale"), currency: fd.get("currency"), wish: fd.get("wish") || null,
          whatsapp_consent_confirmed: fd.get("consent") === "on",
          names: names.filter((n) => n.name.trim()).map((n) => ({ ...n, gotra: n.gotra_unknown ? null : n.gotra, nakshatra: n.nakshatra || null })),
        } })), "Booking created and payment link sent on WhatsApp.");
      }}>
        <Field label="Devotee WhatsApp number (E.164)"><input name="phone" required pattern="^\+[1-9]\d{7,14}$" className="pp-input" placeholder="+919876543210" /></Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Language"><select name="locale" className="pp-input">{["te", "hi", "ta", "en"].map((l) => <option key={l}>{l}</option>)}</select></Field>
          <Field label="Currency"><select name="currency" className="pp-input"><option>INR</option><option>USD</option></select></Field>
        </div>
        <Field label="Puja"><select className="pp-input" required onChange={(e) => setPujaId(Number(e.target.value) || null)} defaultValue="">
          <option value="">Choose…</option>{(pujas.data ?? []).filter((p) => p.status === "published").map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select></Field>
        <Field label="Date"><select name="event" className="pp-input" required>
          {(events.data ?? []).filter((e) => new Date(e.booking_cutoff_at).getTime() > now).map((e) => <option key={e.id} value={e.id}>{fmtDate(e.starts_at)}</option>)}
        </select></Field>
        <Field label="Package"><select name="package" className="pp-input" required>
          {(detail.data?.packages ?? []).map((p) => <option key={p.id} value={p.id}>{p.label} · {p.max_names} names · {inr(p.prices.INR)}</option>)}
        </select></Field>
        {names.map((n, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-4">
            <input className="pp-input" placeholder={`Name ${i + 1}`} value={n.name} onChange={(e) => setName(i, { name: e.target.value })} />
            <input className="pp-input" placeholder="Gotra" value={n.gotra} disabled={n.gotra_unknown} onChange={(e) => setName(i, { gotra: e.target.value })} />
            <input className="pp-input" placeholder="Nakshatra" value={n.nakshatra} onChange={(e) => setName(i, { nakshatra: e.target.value })} />
            <label className="flex items-center gap-2 text-small"><input type="checkbox" checked={n.gotra_unknown} onChange={(e) => setName(i, { gotra_unknown: e.target.checked })} /> gotra unknown</label>
          </div>
        ))}
        <button type="button" className="pp-link" onClick={() => setNames([...names, { name: "", gotra: "", gotra_unknown: false, nakshatra: "" }])}>+ add name</button>
        <Field label="Wish (optional, 140)"><input name="wish" maxLength={140} className="pp-input" /></Field>
        <label className="flex items-center gap-2"><input name="consent" type="checkbox" required /> The devotee agreed on the call to receive updates and proof on WhatsApp</label>
        <button className="pp-btn pp-btn-primary" disabled={busy}>Create booking and send payment link</button>
      </form>
    </>
  );
}
