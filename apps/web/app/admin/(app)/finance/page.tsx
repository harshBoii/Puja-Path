"use client";
import Link from "next/link";

import { Badge, Card, PageTitle, Table, fmtDate, inr, statusTone, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

type Pay = { id: string; booking_id: string | null; provider: string; order_id: string; payment_id: string | null; amount_minor: number;
  currency: string; status: string; at: string; settled: boolean };
type Ref = { id: string; booking_id: string | null; amount_minor: number; reason: string; status: string; provider_refund_id: string | null; at: string };
type Mis = { id: number; date: string; provider: string; kind: string; provider_payment_id: string | null; detail: Record<string, unknown> };

export default function Finance() {
  const pays = useApi<Pay[]>("/admin/finance/payments");
  const refs = useApi<Ref[]>("/admin/finance/refunds");
  const mis = useApi<Mis[]>("/admin/finance/mismatches");
  const { run, view } = useAction();
  return (
    <>
      <PageTitle actions={<a className="pp-btn pp-btn-secondary" href="/api/v1/admin/finance/export.csv">Export CSV (30 days)</a>}>Finance</PageTitle>
      {view}
      <Card title="Reconciliation mismatches">
        <Table head={["Date", "Provider", "Kind", "Payment", "Detail", ""]} rows={(mis.data ?? []).map((m) => [m.date, m.provider, <Badge key="k" tone="red">{m.kind}</Badge>,
          m.provider_payment_id, <code key="d" className="text-small">{JSON.stringify(m.detail)}</code>,
          <button key="r" className="pp-link" onClick={() => run(async () => { await api(`/admin/finance/mismatches/${m.id}/resolve`, { method: "POST" }); mis.reload(); }, "Resolved.")}>Resolve</button>])}
          empty="No open mismatches." />
      </Card>
      <Card title="Payments (30 days)">
        <Table head={["When", "Booking", "Provider", "Order / payment", "Amount", "Status", "Settled"]} rows={(pays.data ?? []).map((p) => [fmtDate(p.at),
          p.booking_id ? <Link key="b" href={`/admin/bookings/${p.booking_id}`} className="pp-link">open</Link> : "subscription", p.provider,
          <span key="o" className="text-small">{p.order_id}<br />{p.payment_id}</span>, inr(p.amount_minor, p.currency),
          <Badge key="s" tone={statusTone(p.status)}>{p.status}</Badge>, p.settled ? "yes" : "—"])} />
      </Card>
      <Card title="Refunds">
        <Table head={["When", "Booking", "Amount", "Reason", "Status", "Reference"]} rows={(refs.data ?? []).map((r) => [fmtDate(r.at),
          r.booking_id ? <Link key="b" href={`/admin/bookings/${r.booking_id}`} className="pp-link">open</Link> : "—", inr(r.amount_minor), r.reason,
          <Badge key="s" tone={statusTone(r.status)}>{r.status}</Badge>, r.provider_refund_id])} />
      </Card>
    </>
  );
}
