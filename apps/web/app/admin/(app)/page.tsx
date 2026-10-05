"use client";
import Link from "next/link";

import { Badge, Card, PageTitle, Table, fmtDate, useApi, useStaff } from "@/components/admin/ui";

type Ev = { id: number; title: string; starts_at: string; booking_count: number; status: string };
type Sla = { groups: { event_id: number; title: string; bookings: { state: string }[] }[] };
type B = { id: string; code: string; name: string | null; phone: string; needs_call_reason: string | null; title: string };
type Cb = { id: number; phone: string; name: string | null; handled: boolean; at: string };

export default function Dashboard() {
  const staff = useStaff();
  const role = staff?.role ?? "";
  const ops = ["admin", "ops_coordinator"].includes(role);
  const support = ["admin", "support_agent"].includes(role);
  const today = useApi<{ events: Ev[] }>(ops ? "/admin/today" : null);
  const sla = useApi<Sla>(ops || support ? "/admin/sla" : null);
  const calls = useApi<B[]>(support ? "/admin/bookings?call_queue=true" : null);
  const cbs = useApi<Cb[]>(support ? "/admin/callback-requests" : null);
  const breached = sla.data?.groups.flatMap((g) => g.bookings).filter((b) => b.state === "breached").length ?? 0;
  const atRisk = sla.data?.groups.flatMap((g) => g.bookings).filter((b) => b.state === "at_risk").length ?? 0;
  return (
    <>
      <PageTitle>Namaste, {staff?.name}</PageTitle>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        {ops && <Card title="Today's events"><p className="font-display text-display">{today.data?.events.length ?? "…"}</p><Link href="/admin/today" className="pp-link">Open queue</Link></Card>}
        {(ops || support) && <Card title="SLA"><p><Badge tone="red">{breached} breached</Badge> <Badge>{atRisk} at risk</Badge></p><Link href="/admin/sla" className="pp-link">Open SLA board</Link></Card>}
        {support && <Card title="Call queue"><p className="font-display text-display">{calls.data?.length ?? "…"}</p><p className="text-small text-ink-600">WhatsApp could not reach these devotees.</p></Card>}
      </div>
      {ops && today.data && (
        <Card title="Today">
          <Table head={["Time (IST)", "Puja", "Bookings", "Status"]} rows={today.data.events.map((e) => [
            fmtDate(e.starts_at), <Link key="l" href={`/admin/events/${e.id}`} className="pp-link">{e.title}</Link>, e.booking_count, <Badge key="s">{e.status}</Badge>])} />
        </Card>
      )}
      {support && calls.data && calls.data.length > 0 && (
        <Card title="Call queue">
          <Table head={["Code", "Name", "Phone", "Reason"]} rows={calls.data.map((b) => [
            <Link key="c" href={`/admin/bookings/${b.id}`} className="pp-link">{b.code}</Link>, b.name, b.phone, b.needs_call_reason])} />
        </Card>
      )}
      {support && cbs.data && (
        <Card title="Callback requests">
          <Table head={["Requested", "Name", "Phone", ""]} rows={cbs.data.filter((c) => !c.handled).map((c) => [fmtDate(c.at), c.name, c.phone,
            <button key="h" className="pp-link" onClick={async () => { await fetch(`/api/v1/admin/callback-requests/${c.id}/handled`, { method: "POST" }); cbs.reload(); }}>Mark handled</button>])}
            empty="No open requests." />
        </Card>
      )}
    </>
  );
}
