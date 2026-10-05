"use client";
import { DiyaLoader } from "@pujapath/ui";
import Link from "next/link";
import { useState } from "react";

import { Badge, Card, PageTitle, fmtDate, statusTone, useApi } from "@/components/admin/ui";

type Ev = { id: number; title: string; temple: string; starts_at: string; booking_count: number; status: string; locked: boolean;
  sankalp_video: boolean; sla_due_at: string };

/** Today's events in time order; each opens the per-event ops flow. Works on a phone. */
export default function Today() {
  const [day, setDay] = useState("");
  const { data } = useApi<{ date: string; events: Ev[]; carry_over: Ev[] }>(`/admin/today${day ? `?day=${day}` : ""}`);
  const list = (evs: Ev[]) => evs.map((e) => (
    <li key={e.id}>
      <Link href={`/admin/events/${e.id}`} className="pp-card flex flex-col gap-1 p-4 text-ink-900 no-underline">
        <span className="flex items-center justify-between gap-2"><span className="font-semibold">{fmtDate(e.starts_at)}</span>
          <Badge tone={statusTone(e.status)}>{e.status}</Badge></span>
        <span className="text-h3">{e.title}</span>
        <span className="text-small text-ink-600">{e.temple} · {e.booking_count} bookings · SLA due {fmtDate(e.sla_due_at)}</span>
      </Link>
    </li>
  ));
  return (
    <>
      <PageTitle actions={<input type="date" className="pp-input w-auto" value={day} onChange={(e) => setDay(e.target.value)} aria-label="Day" />}>
        Today {data && <span className="text-h3 text-ink-600">· {data.date}</span>}
      </PageTitle>
      {!data ? <DiyaLoader label="Loading…" /> : (
        <>
          <ul className="space-y-3">{data.events.length ? list(data.events) : <p className="text-ink-600">No events on this day.</p>}</ul>
          {data.carry_over.length > 0 && <Card title="Earlier events still awaiting proof" className="mt-6"><ul className="space-y-3">{list(data.carry_over)}</ul></Card>}
        </>
      )}
    </>
  );
}
