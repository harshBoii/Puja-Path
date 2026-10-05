"use client";
import { DiyaLoader } from "@pujapath/ui";
import { use, useState } from "react";

import { Badge, Card, Field, PageTitle, Table, fmtDate, inr, statusTone, useAction, useApi, useStaff } from "@/components/admin/ui";
import { api } from "@/lib/client";

type D = {
  id: string; code: string; status: string; locale: string; currency: string; title: string; temple: string;
  event: { id: number; starts_at: string; cutoff: string; status: string }; package: string; max_names: number;
  names: { name: string; relation: string | null; gotra: string | null; gotra_unknown: boolean; nakshatra: string | null }[];
  wish: string | null; phone: string; user: { id: string; name: string | null } | null;
  pricing: Record<string, number>; timestamps: Record<string, string | null>; cancel_reason: string | null;
  needs_call_reason: string | null; before_cutoff: boolean;
  payments: { id: string; provider: string; order_id: string; payment_id: string | null; amount_minor: number; status: string }[];
  refunds: { id: string; amount_minor: number; reason: string; status: string; provider_refund_id: string | null }[];
  shipment: { status: string; awb: string | null; courier: string | null; address: Record<string, string>; events: { status: string; at: string }[] } | null;
  messages: { id: string; template: string; status: string; error: string | null; scheduled_for: string | null; sent_at: string | null;
    delivered_at: string | null; read_at: string | null; provider: string }[];
  notes: { text: string; by: string; at: string }[]; proof_path: string;
};

export default function BookingAdmin({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const staff = useStaff();
  const { data: b, reload } = useApi<D>(`/admin/bookings/${id}`);
  const { run, busy, view } = useAction();
  const [names, setNames] = useState<D["names"] | null>(null);
  if (!b) return <DiyaLoader label="Loading…" />;
  const canSupport = ["admin", "support_agent"].includes(staff?.role ?? "");
  const canRefund = ["admin", "support_agent", "finance"].includes(staff?.role ?? "");
  const edit = names ?? b.names;
  return (
    <>
      <PageTitle actions={<Badge tone={statusTone(b.status)}>{b.status}</Badge>}>{b.code}</PageTitle>
      <p className="-mt-3 mb-4 text-ink-600">{b.title} · {b.temple} · {fmtDate(b.event.starts_at)} · {b.package} · {b.locale} · {b.phone}</p>
      {b.needs_call_reason && <p className="mb-3 rounded-btn bg-gold-100 p-3">Call queue: {b.needs_call_reason}</p>}
      {view}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Timeline">
          <Table head={["Event", "At"]} rows={Object.entries(b.timestamps).map(([k, v]) => [k.replace("_at", ""), fmtDate(v)])} />
          {b.cancel_reason && <p className="mt-2">Cancel reason: {b.cancel_reason}</p>}
          <a className="pp-link mt-2 inline-block" href={`/${b.proof_path}`} target="_blank" rel="noreferrer">Proof page</a>
        </Card>
        <Card title="Names" actions={canSupport && <span className="text-small text-ink-600">{b.before_cutoff ? "editable until cutoff" : "after cutoff: needs a reason"}</span>}>
          {edit.map((n, i) => (
            <div key={i} className="mb-2 grid gap-2 sm:grid-cols-3">
              <input className="pp-input" value={n.name} disabled={!canSupport} aria-label="Name"
                onChange={(e) => setNames(edit.map((x, k) => (k === i ? { ...x, name: e.target.value } : x)))} />
              <input className="pp-input" value={n.gotra ?? ""} disabled={!canSupport || n.gotra_unknown} aria-label="Gotra" placeholder={n.gotra_unknown ? "fallback" : "gotra"}
                onChange={(e) => setNames(edit.map((x, k) => (k === i ? { ...x, gotra: e.target.value } : x)))} />
              <input className="pp-input" value={n.nakshatra ?? ""} disabled={!canSupport} aria-label="Nakshatra" placeholder="nakshatra"
                onChange={(e) => setNames(edit.map((x, k) => (k === i ? { ...x, nakshatra: e.target.value } : x)))} />
            </div>
          ))}
          {b.wish && <p className="text-small">Wish: {b.wish}</p>}
          {canSupport && names && (
            <button className="pp-btn pp-btn-primary mt-2" disabled={busy} onClick={() => {
              const reason = b.before_cutoff ? null : window.prompt("Reason for editing after cutoff (audited):");
              if (!b.before_cutoff && !reason) return;
              run(async () => { await api(`/admin/bookings/${id}/names`, { method: "PUT", json: { names, reason } }); setNames(null); reload(); }, "Names saved.");
            }}>Save names</button>
          )}
        </Card>
        <Card title="Payments and refunds">
          <Table head={["Provider", "Order", "Payment", "Amount", "Status"]} rows={b.payments.map((p) => [p.provider, p.order_id, p.payment_id, inr(p.amount_minor, b.currency),
            <Badge key="s" tone={statusTone(p.status)}>{p.status}</Badge>])} />
          {b.refunds.length > 0 && <div className="mt-3"><Table head={["Refund", "Amount", "Reason", "Status"]} rows={b.refunds.map((r) => [
            r.provider_refund_id, inr(r.amount_minor, b.currency), r.reason, <Badge key="s" tone={statusTone(r.status)}>{r.status}</Badge>])} /></div>}
          <p className="mt-2 text-small">Total {inr(b.pricing.total, b.currency)} (package {inr(b.pricing.subtotal, b.currency)}, add-ons {inr(b.pricing.addons, b.currency)},
            shipping {inr(b.pricing.shipping, b.currency)}, dakshina {inr(b.pricing.dakshina, b.currency)})</p>
          {canRefund && (
            <div className="mt-3 flex flex-wrap gap-2">
              {!["cancelled", "refunded", "completed"].includes(b.status) && (
                <button className="pp-btn border border-sindoor-600 text-sindoor-600" disabled={busy} onClick={() => {
                  const reason = window.prompt("Cancellation reason:");
                  if (reason) run(async () => { await api(`/admin/bookings/${id}/cancel`, { method: "POST", json: { reason } }); reload(); }, "Cancelled and refunded.");
                }}>Cancel and refund</button>
              )}
              <button className="pp-btn pp-btn-secondary" disabled={busy} onClick={() => {
                const amt = window.prompt("Partial refund amount (in rupees/dollars):");
                const reason = amt && window.prompt("Reason (e.g. add-on could not ship):");
                if (amt && reason) run(async () => { await api(`/admin/bookings/${id}/refund`, { method: "POST",
                  json: { amount_minor: Math.round(Number(amt) * 100), reason } }); reload(); }, "Refund requested.");
              }}>Partial refund</button>
            </div>
          )}
        </Card>
        {b.shipment && (
          <Card title="Shipment">
            <p><Badge tone={statusTone(b.shipment.status)}>{b.shipment.status}</Badge> {b.shipment.courier} {b.shipment.awb}</p>
            <p className="mt-1 text-small text-ink-600">{Object.values(b.shipment.address).filter((v) => typeof v === "string").join(", ")}</p>
            <ul className="mt-2 text-small">{b.shipment.events.map((e, i) => <li key={i}>{e.status} · {fmtDate(e.at)}</li>)}</ul>
          </Card>
        )}
      </div>
      <Card title="WhatsApp messages">
        <Table head={["Template", "Status", "Scheduled", "Sent", "Delivered", "Read", ""]} rows={b.messages.map((m) => [
          m.template, <Badge key="s" tone={statusTone(m.status)}>{m.status}{m.error ? ` · ${m.error}` : ""}</Badge>, fmtDate(m.scheduled_for),
          fmtDate(m.sent_at), fmtDate(m.delivered_at), fmtDate(m.read_at),
          canSupport ? <button key="r" className="pp-link" onClick={() => run(async () => { await api(`/admin/messages/${m.id}/resend`, { method: "POST" }); reload(); }, "Queued again.")}>Resend</button> : null])} />
      </Card>
      <Card title="Notes">
        <ul className="mb-3 space-y-1">{b.notes.map((n, i) => <li key={i}><span className="text-small text-ink-600">{n.by} · {fmtDate(n.at)}:</span> {n.text}</li>)}</ul>
        <form className="flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const text = String(new FormData(form).get("text") ?? "");
          if (text) run(async () => { await api(`/admin/bookings/${id}/notes`, { method: "POST", json: { text } }); form.reset(); reload(); }, "Note added.");
        }}>
          <Field label="Add a note"><input name="text" className="pp-input" /></Field>
          <button className="pp-btn pp-btn-secondary self-end">Add</button>
          {b.needs_call_reason && canSupport && <button type="button" className="pp-btn pp-btn-secondary self-end" onClick={() => {
            const text = window.prompt("Call outcome:");
            if (text) run(async () => { await api(`/admin/bookings/${id}/clear-call-queue`, { method: "POST", json: { text } }); reload(); }, "Cleared.");
          }}>Clear call queue</button>}
        </form>
      </Card>
    </>
  );
}
