"use client";
// Dates (puja events): list, filter, add one or a repeating series, edit, delete. Used on the Events page and
// inside each puja's editor. The API enforces the same rules the buttons reflect (can_edit_* / can_delete).
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Badge, Field, Table, fmtDate, statusTone, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

export type AdminEvent = {
  id: number; puja_id: number; puja_kind: string; title: string; temple: string; starts_at: string; booking_cutoff_at: string;
  cutoff_hours: number; video_sla_hours: number; sla_due_at: string; status: string; booking_count: number;
  payments_in_progress: number; can_edit_time: boolean; can_edit_cutoff: boolean; can_edit_sla: boolean; can_delete: boolean;
};
type PujaOpt = { id: number; title: string; kind: string };

/** ISO instant -> value for <input type="datetime-local"> in IST (all ops times are IST). */
export function toIstInput(iso: string): string {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

const num = (v: FormDataEntryValue | null) => (v === null || v === "" ? null : Number(v));

const REPEATS: [string, string][] = [
  ["FREQ=DAILY", "Every day"],
  ...["MO", "TU", "WE", "TH", "FR", "SA", "SU"].map((d, i): [string, string] =>
    [`FREQ=WEEKLY;BYDAY=${d}`, `Every ${["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][i]}`]),
  ["FREQ=MONTHLY", "Every month (same date)"],
];

export function EventsManager({ pujaId, initialPujaId }: { pujaId?: number; initialPujaId?: number | null }) {
  const [filterPuja, setFilterPuja] = useState<number | null>(initialPujaId ?? null);
  const [when, setWhen] = useState<"upcoming" | "past" | "all">("upcoming");
  const [status, setStatus] = useState("");
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<AdminEvent | null>(null);
  const puja = pujaId ?? filterPuja;
  const qs = new URLSearchParams({ when, ...(puja ? { puja_id: String(puja) } : {}), ...(status ? { status } : {}) });
  const evs = useApi<AdminEvent[]>(`/admin/events?${qs}`);
  const pujas = useApi<PujaOpt[]>(pujaId ? null : "/admin/pujas");
  const { run, view } = useAction();

  const remove = (e: AdminEvent) => {
    if (!window.confirm(`Delete the ${fmtDate(e.starts_at)} date of “${e.title}”? This can't be undone.`)) return;
    return run(async () => {
      const r = await api<{ result: string }>(`/admin/events/${e.id}`, { method: "DELETE" });
      evs.reload();
      return r.result;
    }, (result) => result === "cancelled"
      ? "Date cancelled and hidden from the site (kept for records because it had unfinished checkouts or media)."
      : "Date deleted.");
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        {!pujaId && (
          <div className="min-w-56 flex-1"><Field label="Puja">
            <select className="pp-input" value={filterPuja ?? ""} onChange={(e) => setFilterPuja(Number(e.target.value) || null)}>
              <option value="">All pujas</option>{(pujas.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.title} ({p.kind})</option>)}
            </select></Field></div>
        )}
        <Field label="Show"><select className="pp-input" value={when} onChange={(e) => setWhen(e.target.value as typeof when)}>
          <option value="upcoming">Upcoming</option><option value="past">Past</option><option value="all">All</option></select></Field>
        <Field label="Status"><select className="pp-input" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any</option>{["scheduled", "started", "performed", "disrupted", "cancelled"].map((s) => <option key={s}>{s}</option>)}
        </select></Field>
        <button type="button" className="pp-btn pp-btn-primary" onClick={() => setAdding((a) => !a)} aria-expanded={adding}>
          {adding ? "Close" : "+ Add dates"}</button>
      </div>
      {view}
      {adding && <AddDates pujaId={puja} pujas={pujaId ? null : pujas.data} onDone={() => { evs.reload(); }} />}
      {!evs.data ? <p className="text-ink-600">Loading dates…</p> : (
        <Table empty="No dates match these filters." head={["Starts (IST)", ...(pujaId ? [] : ["Puja"]), "Booking closes", "Video due", "Bookings", "Status", ""]}
          rows={evs.data.map((e) => [
            <Link key="s" href={`/admin/events/${e.id}`} className="pp-link font-semibold">{fmtDate(e.starts_at)}</Link>,
            ...(pujaId ? [] : [<span key="p">{e.title}<br /><span className="text-ink-600">{e.temple}</span></span>]),
            <span key="c">{fmtDate(e.booking_cutoff_at)}<br /><span className="text-ink-600">{e.cutoff_hours} h before</span></span>,
            <span key="v">{fmtDate(e.sla_due_at)}<br /><span className="text-ink-600">{e.video_sla_hours} h after</span></span>,
            <span key="b">{e.booking_count}{e.payments_in_progress ? <span className="text-ink-600"> (+{e.payments_in_progress} paying)</span> : null}</span>,
            <Badge key="st" tone={statusTone(e.status)}>{e.status}</Badge>,
            <span key="a" className="flex flex-wrap gap-2">
              <button type="button" className="pp-btn pp-btn-secondary min-h-9 px-3" onClick={() => setEditing(e)}>Edit</button>
              <Link href={`/admin/events/${e.id}`} className="pp-btn pp-btn-secondary min-h-9 px-3">Run</Link>
              {e.can_delete && <button type="button" className="pp-btn min-h-9 border border-sindoor-600 px-3 text-sindoor-600" onClick={() => remove(e)}>Delete</button>}
            </span>,
          ])} />
      )}
      {editing && (
        <Dialog title={`Edit date · ${editing.title}`} onClose={() => setEditing(null)}>
          <EventEditForm ev={editing} onSaved={() => { setEditing(null); evs.reload(); }} onDeleted={() => { setEditing(null); evs.reload(); }} />
        </Dialog>
      )}
    </div>
  );
}

function AddDates({ pujaId, pujas, onDone }: { pujaId: number | null; pujas: PujaOpt[] | null; onDone: () => void }) {
  const [mode, setMode] = useState<"one" | "repeat">("one");
  const [target, setTarget] = useState<number | null>(pujaId);
  const [rrule, setRrule] = useState(REPEATS[1][0]);
  const { run, busy, view } = useAction();
  useEffect(() => setTarget(pujaId), [pujaId]); // eslint-disable-line react-hooks/set-state-in-effect -- follow the page filter
  return (
    <div className="mb-4 rounded-card border border-gold-line bg-surface p-4">
      {view}
      <div className="mb-3 flex flex-wrap gap-2" role="tablist">
        <button type="button" role="tab" className="pp-chip" aria-selected={mode === "one"} data-selected={mode === "one"} onClick={() => setMode("one")}>One date</button>
        <button type="button" role="tab" className="pp-chip" aria-selected={mode === "repeat"} data-selected={mode === "repeat"} onClick={() => setMode("repeat")}>Repeating dates</button>
      </div>
      <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        const common = { puja_id: target, cutoff_hours: num(fd.get("cutoff")), video_sla_hours: num(fd.get("sla")) };
        run(async () => {
          if (mode === "one") await api("/admin/events", { method: "POST", json: { ...common, starts_at: fd.get("starts_at") } });
          else await api("/admin/events/series", { method: "POST", json: { ...common, rrule, first_starts_at: fd.get("starts_at"), count: num(fd.get("count")) } });
          onDone();
        }, mode === "one" ? "Date added." : "Dates added.");
      }}>
        {pujas && (
          <div className="sm:col-span-2 lg:col-span-4"><Field label="Puja">
            <select className="pp-input" required value={target ?? ""} onChange={(e) => setTarget(Number(e.target.value) || null)}>
              <option value="">Choose a puja…</option>{pujas.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.kind})</option>)}
            </select></Field></div>
        )}
        <Field label={mode === "one" ? "Starts at (IST)" : "First date (IST)"}><input name="starts_at" type="datetime-local" required className="pp-input" /></Field>
        {mode === "repeat" && <>
          <Field label="Repeats"><select className="pp-input" value={rrule} onChange={(e) => setRrule(e.target.value)}>
            {REPEATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="How many dates"><input name="count" type="number" min={1} max={104} defaultValue={8} required className="pp-input" /></Field>
        </>}
        <Field label="Booking closes (hours before)" hint="Empty = site default"><input name="cutoff" type="number" min={1} max={240} step="0.5" className="pp-input" /></Field>
        <Field label="Video due (hours after)" hint="Empty = puja default"><input name="sla" type="number" min={1} max={720} className="pp-input" /></Field>
        <div className="flex items-end sm:col-span-2 lg:col-span-4">
          <button className="pp-btn pp-btn-primary" disabled={!target || busy}>{mode === "one" ? "Add date" : "Add dates"}</button>
        </div>
      </form>
    </div>
  );
}

/** Edit one date. Fields the rules don't allow are shown disabled with the reason. */
export function EventEditForm({ ev, onSaved, onDeleted }: { ev: AdminEvent; onSaved: () => void; onDeleted?: () => void }) {
  const { run, busy, view } = useAction();
  const lockedReason = ev.booking_count || ev.payments_in_progress
    ? "Devotees have paid: move this date with “Reschedule” on the event page, so they are told and can choose a refund."
    : ev.status !== "scheduled" ? `This event is ${ev.status}.` : "The sankalp sheet is locked.";
  return (
    <form className="space-y-3" onSubmit={(e) => {
      e.preventDefault();
      const fd = new FormData(e.currentTarget);
      const body: Record<string, unknown> = {};
      const starts = String(fd.get("starts_at") ?? "");
      if (ev.can_edit_time && starts && starts !== toIstInput(ev.starts_at)) body.starts_at = starts;
      const cutoff = num(fd.get("cutoff"));
      if (ev.can_edit_cutoff && cutoff !== null && cutoff !== ev.cutoff_hours) body.cutoff_hours = cutoff;
      const sla = num(fd.get("sla"));
      if (ev.can_edit_sla && sla !== null && sla !== ev.video_sla_hours) body.video_sla_hours = sla;
      run(async () => { if (Object.keys(body).length) await api(`/admin/events/${ev.id}`, { method: "PATCH", json: body }); onSaved(); }, "Date saved.");
    }}>
      {view}
      <Field label="Starts at (IST)" hint={ev.can_edit_time ? undefined : lockedReason}>
        <input name="starts_at" type="datetime-local" className="pp-input" defaultValue={toIstInput(ev.starts_at)} disabled={!ev.can_edit_time} required />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Booking closes (hours before)" hint={ev.can_edit_cutoff ? `Now: ${fmtDate(ev.booking_cutoff_at)}` : "Locked"}>
          <input name="cutoff" type="number" min={0.5} max={240} step="0.5" className="pp-input" defaultValue={ev.cutoff_hours} disabled={!ev.can_edit_cutoff} />
        </Field>
        <Field label="Video due (hours after)" hint={ev.can_edit_sla ? `Now due: ${fmtDate(ev.sla_due_at)}` : "Closed"}>
          <input name="sla" type="number" min={1} max={720} className="pp-input" defaultValue={ev.video_sla_hours} disabled={!ev.can_edit_sla} />
        </Field>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <button className="pp-btn pp-btn-primary" disabled={busy || !(ev.can_edit_time || ev.can_edit_cutoff || ev.can_edit_sla)}>Save</button>
        {ev.can_delete && onDeleted && (
          <button type="button" className="pp-btn border border-sindoor-600 text-sindoor-600" disabled={busy} onClick={() => {
            if (!window.confirm("Delete this date? This can't be undone.")) return;
            run(async () => { const r = await api<{ result: string }>(`/admin/events/${ev.id}`, { method: "DELETE" }); onDeleted(); return r.result; },
              (result) => (result === "cancelled" ? "Date cancelled and hidden from the site." : "Date deleted."));
          }}>Delete date</button>
        )}
      </div>
    </form>
  );
}

function Dialog({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return (
    <dialog ref={ref} onClose={onClose} className="pp-card m-auto w-[min(34rem,calc(100vw-2rem))] p-5 backdrop:bg-ink-900/40">
      <div className="mb-4 flex items-start justify-between gap-3">
        <h2 className="text-h3">{title}</h2>
        <button type="button" className="pp-link min-h-9" onClick={() => ref.current?.close()} aria-label="Close">✕</button>
      </div>
      {children}
    </dialog>
  );
}
