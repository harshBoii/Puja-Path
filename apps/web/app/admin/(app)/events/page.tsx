"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Badge, Card, Field, PageTitle, Table, fmtDate, statusTone, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

type Ev = { id: number; puja_id: number; title: string; starts_at: string; booking_cutoff_at: string; video_sla_hours: number;
  booking_count: number; status: string };
type P = { id: number; title: string; kind: string };

export default function EventsPage() {
  return <Suspense><Events /></Suspense>;
}

/** Create one event, or generate a series from a seva's recurrence rule. Each shows cutoff, SLA, bookings, status. */
function Events() {
  const sp = useSearchParams();
  const [pujaId, setPujaId] = useState<number | null>(sp.get("puja_id") ? Number(sp.get("puja_id")) : null);
  const pujas = useApi<P[]>("/admin/pujas");
  const evs = useApi<Ev[]>(`/admin/events${pujaId ? `?puja_id=${pujaId}` : ""}`);
  const { run, busy, view } = useAction();
  return (
    <>
      <PageTitle>Events</PageTitle>
      {view}
      <Card title="Add events">
        <div className="grid gap-4 lg:grid-cols-2">
          <form className="space-y-2" onSubmit={(e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            run(async () => { await api("/admin/events", { method: "POST", json: { puja_id: pujaId, starts_at: fd.get("starts_at"),
              cutoff_hours: fd.get("cutoff") ? Number(fd.get("cutoff")) : null, video_sla_hours: fd.get("sla") ? Number(fd.get("sla")) : null } }); evs.reload(); }, "Event created.");
          }}>
            <p className="font-semibold">Single event</p>
            <Field label="Starts at (IST)"><input name="starts_at" type="datetime-local" required className="pp-input" /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Cutoff hours before" hint="empty = site default"><input name="cutoff" type="number" className="pp-input" /></Field>
              <Field label="Video SLA hours" hint="empty = puja/site default"><input name="sla" type="number" className="pp-input" /></Field>
            </div>
            <button className="pp-btn pp-btn-primary" disabled={!pujaId || busy}>Create event</button>
          </form>
          <form className="space-y-2" onSubmit={(e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            run(async () => { const r = await api<{ created: number[] }>("/admin/events/series", { method: "POST", json: { puja_id: pujaId,
              rrule: fd.get("rrule"), first_starts_at: fd.get("first"), count: Number(fd.get("count")) } }); evs.reload(); return r; }, "Series created.");
          }}>
            <p className="font-semibold">Series from a recurrence rule</p>
            <Field label="RRULE"><input name="rrule" defaultValue="FREQ=WEEKLY;BYDAY=TU" className="pp-input" /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="First occurrence (IST)"><input name="first" type="datetime-local" required className="pp-input" /></Field>
              <Field label="Count"><input name="count" type="number" defaultValue={7} className="pp-input" /></Field>
            </div>
            <button className="pp-btn pp-btn-secondary" disabled={!pujaId || busy}>Generate series</button>
          </form>
        </div>
      </Card>
      <div className="mb-3 max-w-md">
        <Field label="Puja"><select className="pp-input" value={pujaId ?? ""} onChange={(e) => setPujaId(Number(e.target.value) || null)}>
          <option value="">All pujas</option>{(pujas.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.title} ({p.kind})</option>)}
        </select></Field>
      </div>
      <Table head={["Starts (IST)", "Puja", "Cutoff", "SLA", "Bookings", "Status"]} rows={(evs.data ?? []).map((e) => [
        <Link key="s" href={`/admin/events/${e.id}`} className="pp-link">{fmtDate(e.starts_at)}</Link>, e.title, fmtDate(e.booking_cutoff_at),
        `${e.video_sla_hours} h`, e.booking_count, <Badge key="b" tone={statusTone(e.status)}>{e.status}</Badge>])} />
    </>
  );
}
