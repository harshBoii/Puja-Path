"use client";
import { DiyaLoader } from "@pujapath/ui";
import Link from "next/link";

import { Badge, Card, PageTitle, Table, fmtDate, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

type Board = { as_of: string; groups: { event_id: number; title: string; starts_at: string; due_at: string; event_status: string;
  bookings: { id: string; code: string; status: string; state: string; refund_due: boolean; delay_notified: boolean }[] }[] };

/** At risk = 6 h before breach; breached = past SLA. Grouped by event with one-tap escalate. */
export default function SlaBoard() {
  const { data, reload } = useApi<Board>("/admin/sla");
  const { run, view } = useAction();
  return (
    <>
      <PageTitle actions={<button className="pp-btn pp-btn-secondary" onClick={reload}>Refresh</button>}>SLA board</PageTitle>
      {view}
      {!data ? <DiyaLoader label="Loading…" /> : data.groups.length === 0 ? <p className="text-ink-600">Nothing at risk. As of {fmtDate(data.as_of)}.</p> : data.groups.map((g) => (
        <Card key={g.event_id} title={<Link href={`/admin/events/${g.event_id}`} className="pp-link">{g.title}</Link>}
          actions={<button className="pp-btn pp-btn-secondary min-h-10" onClick={() => {
            const note = window.prompt("Escalation note (sent to ops by email and Slack):");
            if (note) run(() => api(`/admin/sla/${g.event_id}/escalate`, { method: "POST", json: { note } }), "Escalated.");
          }}>Escalate</button>}>
          <p className="mb-2 text-small text-ink-600">Puja {fmtDate(g.starts_at)} · SLA due {fmtDate(g.due_at)} · event {g.event_status}</p>
          <Table head={["Booking", "Status", "SLA", "Delay message", ""]} rows={g.bookings.map((b) => [
            <Link key="c" href={`/admin/bookings/${b.id}`} className="pp-link">{b.code}</Link>, b.status,
            <Badge key="s" tone={b.state === "breached" ? "red" : "gold"}>{b.state.replace("_", " ")}</Badge>,
            b.delay_notified ? "sent" : "—", b.refund_due ? <Badge key="r" tone="red">refund due</Badge> : null])} />
        </Card>
      ))}
    </>
  );
}
