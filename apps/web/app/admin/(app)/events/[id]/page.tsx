"use client";
import { DiyaLoader } from "@pujapath/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useMemo, useRef, useState } from "react";

import { EventEditForm, type AdminEvent } from "@/components/admin/EventsManager";
import { Badge, Card, Field, PageTitle, fmtDate, statusTone, useAction, useApi } from "@/components/admin/ui";
import { resumableUpload, type UploadPurpose } from "@/components/admin/upload";
import { api } from "@/lib/client";

type Ev = AdminEvent & { locked: boolean; sankalp_video: boolean; full_video: { url: string } | null; photos: { url: string }[] };
type Row = { position: number; booking_id: string; code: string; status: string; wish: string | null;
  names: { name: string; name_sankalp: string; relation: string | null; gotra: string; gotra_sankalp: string; gotra_unknown: boolean; nakshatra: string | null }[] };
type Clip = { id: string; booking_id: string; code: string; position: number | null; start_ms: number; end_ms: number | null; url: string | null;
  poster: string | null; size_bytes: number | null; qc_status: string; booking_status: string; short: boolean };
type Clips = { sankalp_video_url: string | null; clips: Clip[]; qc: { required_sample: number; short_clip_ids: string[] } };

/** Per event: 1 sheet → 2 Started → 3 uploads → 4 marker tool + QC → 5 Performed (PRD §10.4). */
export default function EventOps({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const ev = useApi<Ev>(`/admin/events/${id}`);
  const sheet = useApi<{ rows: Row[]; sankalp_language: string }>(`/admin/events/${id}/sheet`);
  const clips = useApi<Clips>(`/admin/events/${id}/clips`);
  const { run, busy, view } = useAction();
  const e = ev.data;
  if (!e) return <DiyaLoader label="Loading…" />;
  const reloadAll = () => { ev.reload(); sheet.reload(); clips.reload(); };

  return (
    <>
      <PageTitle actions={<Badge tone={statusTone(e.status)}>{e.status}</Badge>}>{e.title}</PageTitle>
      <p className="-mt-3 mb-4 text-ink-600">{e.temple} · {fmtDate(e.starts_at)} IST · cutoff {fmtDate(e.booking_cutoff_at)} · SLA due {fmtDate(e.sla_due_at)} · {e.booking_count} bookings</p>
      {view}

      <Card title="Date and timings" actions={<Link href={`/admin/catalog/${e.puja_id}`} className="pp-btn pp-btn-secondary min-h-10">Edit puja</Link>}>
        <div className="max-w-xl">
          <EventEditForm key={`${e.starts_at}-${e.booking_cutoff_at}-${e.video_sla_hours}`} ev={e} onSaved={reloadAll}
            onDeleted={() => router.push(`/admin/events?puja_id=${e.puja_id}`)} />
        </div>
      </Card>

      <Card title="1. Sankalp sheet" actions={<div className="flex flex-wrap gap-2">
        {!e.locked && <button className="pp-btn pp-btn-secondary min-h-10" disabled={busy}
          onClick={() => run(async () => { await api(`/admin/events/${id}/lock`, { method: "POST" }); reloadAll(); }, "Sheet locked.")}>Lock now</button>}
        <a className="pp-btn pp-btn-secondary min-h-10" href={`/api/v1/admin/events/${id}/sheet.pdf`} target="_blank" rel="noreferrer">Print PDF</a>
      </div>}>
        {!e.locked && <p className="mb-2 text-small text-ink-600">The sheet is built automatically at the booking cutoff.</p>}
        <ol className="space-y-2">
          {(sheet.data?.rows ?? []).map((r) => (
            <li key={r.booking_id} className="rounded-btn border border-marble-200 p-3">
              <p className="text-small text-ink-600">{r.position}. {r.code}</p>
              {r.names.map((n, i) => (
                <p key={i}><span className="text-h3">{n.name_sankalp || n.name}</span> <span className="text-ink-600">({n.name}{n.relation ? `, ${n.relation}` : ""})</span>
                  {" · "}{n.gotra_sankalp || n.gotra}{n.gotra_unknown && " (fallback)"}{n.nakshatra && ` · ${n.nakshatra}`}</p>
              ))}
              {r.wish && <p className="text-small italic">{r.wish}</p>}
            </li>
          ))}
        </ol>
      </Card>

      <Card title="2. Puja started">
        <p className="mb-2 text-small text-ink-600">Sends <code>puja_started</code> on WhatsApp to every devotee on the sheet.</p>
        <button className="pp-btn pp-btn-primary" disabled={busy || e.status !== "scheduled"}
          onClick={() => run(async () => { const r = await api<{ notified: number }>(`/admin/events/${id}/started`, { method: "POST" }); reloadAll(); return r; }, "Marked started; devotees notified.")}>
          Started
        </button>
      </Card>

      <Card title="3. Uploads">
        <div className="grid gap-4 md:grid-cols-3">
          <Uploader label={`Sankalp video${e.sankalp_video ? " ✓" : ""}`} accept="video/*" purpose="sankalp_video" eventId={e.id} onDone={reloadAll} />
          <Uploader label={`Full ritual video${e.full_video ? " ✓" : ""}`} accept="video/*" purpose="full_video" eventId={e.id} onDone={reloadAll} />
          <Uploader label={`Photos (${e.photos.length})`} accept="image/*" purpose="event_photo" eventId={e.id} onDone={reloadAll} multiple withAlt />
        </div>
        <details className="mt-4"><summary className="cursor-pointer font-semibold">Small events: upload individual clips named {"{booking_code}"}.mp4</summary>
          <div className="mt-2"><Uploader label="Clips" accept="video/mp4" purpose="clips_bulk" eventId={e.id} onDone={reloadAll} multiple /></div>
        </details>
      </Card>

      <Card title="4. Marker tool and QC">
        {clips.data?.sankalp_video_url && sheet.data
          ? <MarkerTool videoUrl={clips.data.sankalp_video_url} rows={sheet.data.rows} eventId={e.id} onSaved={clips.reload} />
          : <p className="text-ink-600">Upload the sankalp video first.</p>}
        {clips.data && clips.data.clips.length > 0 && <Qc eventId={e.id} data={clips.data} onDone={reloadAll} />}
      </Card>

      <Card title="5. Performed">
        <button className="pp-btn pp-btn-primary" disabled={busy || !["scheduled", "started"].includes(e.status)}
          onClick={() => run(async () => { await api(`/admin/events/${id}/performed`, { method: "POST" }); reloadAll(); }, "Marked performed.")}>Performed</button>
      </Card>

      <Card title="Shipping">
        <button className="pp-btn pp-btn-secondary" disabled={busy}
          onClick={() => run(() => api(`/admin/shipping/events/${id}/bulk-create`, { method: "POST" }).then((r) => JSON.stringify(r)), "Shipments booked with the courier.")}>
          Create shipments for this event
        </button>
        <Link href={`/admin/shipping?event_id=${id}`} className="pp-link ml-3">View shipments</Link>
      </Card>

      <Disrupt eventId={e.id} status={e.status} onDone={reloadAll} />
    </>
  );
}

function Uploader({ label, accept, purpose, eventId, onDone, multiple, withAlt }: {
  label: string; accept: string; purpose: UploadPurpose; eventId: number; onDone: () => void; multiple?: boolean; withAlt?: boolean;
}) {
  const [pct, setPct] = useState<number | null>(null);
  const [alt, setAlt] = useState<Record<string, string>>({ en: "", hi: "", ta: "", te: "" });
  const altOk = Object.values(alt).every((v) => v.trim());
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="rounded-btn border border-marble-200 p-3">
      <p className="mb-2 font-semibold">{label}</p>
      {withAlt && (["en", "hi", "ta", "te"] as const).map((l) => (
        <Field key={l} label={`Alt text (${l})`}><input lang={l} className="pp-input mb-2" value={alt[l]}
          onChange={(e) => setAlt((a) => ({ ...a, [l]: e.target.value }))} /></Field>
      ))}
      <input type="file" accept={accept} multiple={multiple} disabled={pct !== null || (withAlt && !altOk)}
        onChange={async (ev) => {
          const files = Array.from(ev.target.files ?? []);
          setErr(null);
          try {
            for (const f of files) {
              setPct(0);
              await resumableUpload(f, { purpose, event_id: eventId, ...(withAlt ? { alt, in_gallery: true } : {}) }, setPct);
            }
            onDone();
          } catch (e) { setErr(String(e)); } finally { setPct(null); ev.target.value = ""; }
        }} />
      {pct !== null && <progress className="mt-2 w-full" max={100} value={pct} aria-label={`${label} upload`} />}
      {err && <p role="alert" className="text-small text-sindoor-600">{err}</p>}
    </div>
  );
}

/** Play the sankalp video; tap "Next name" as each booking's sankalp begins. */
function MarkerTool({ videoUrl, rows, eventId, onSaved }: { videoUrl: string; rows: Row[]; eventId: number; onSaved: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [marks, setMarks] = useState<{ booking_id: string; start_ms: number }[]>([]);
  const { run, busy, view } = useAction();
  const next = rows[marks.length];
  return (
    <div className="mb-6 space-y-3">
      <video ref={video} src={videoUrl} controls playsInline className="w-full max-w-2xl rounded-card bg-ink-900" />
      <div className="sticky bottom-2 z-10 flex flex-wrap items-center gap-2 rounded-btn bg-surface p-2 shadow-card">
        <button className="pp-btn pp-btn-primary min-w-48 text-h3" disabled={!next}
          onClick={() => next && setMarks((m) => [...m, { booking_id: next.booking_id, start_ms: Math.round((video.current?.currentTime ?? 0) * 1000) }])}>
          {next ? `Next name: ${next.position}. ${next.names[0]?.name}` : "All names marked"}
        </button>
        <button className="pp-btn pp-btn-secondary" disabled={!marks.length} onClick={() => setMarks((m) => m.slice(0, -1))}>Undo</button>
        <button className="pp-btn pp-btn-secondary" disabled={!marks.length || busy}
          onClick={() => run(async () => { await api(`/admin/events/${eventId}/markers`, { method: "PUT", json: { markers: marks } }); onSaved(); }, "Markers saved.")}>
          Save {marks.length} markers
        </button>
        <button className="pp-btn pp-btn-secondary" disabled={busy}
          onClick={() => run(() => api(`/admin/events/${eventId}/cut-clips`, { method: "POST" }), "Cutting clips in the background; refresh in a minute.")}>
          Cut clips
        </button>
      </div>
      {view}
      <ol className="grid gap-1 text-small sm:grid-cols-2">{marks.map((m, i) => (
        <li key={m.booking_id}>{rows[i]?.position}. {rows[i]?.code} @ {(m.start_ms / 1000).toFixed(1)} s</li>))}</ol>
    </div>
  );
}

/** QC: spot-check at least 1 in 10 clips and every clip under 5 seconds, then approve the batch. */
function Qc({ eventId, data, onDone }: { eventId: number; data: Clips; onDone: () => void }) {
  const pending = data.clips.filter((c) => c.qc_status === "pending" && c.url);
  const [reviewed, setReviewed] = useState<Set<string>>(new Set());
  const [rejected, setRejected] = useState<Set<string>>(new Set());
  const { run, busy, view } = useAction();
  const short = useMemo(() => new Set(data.qc.short_clip_ids), [data.qc.short_clip_ids]);
  const shortLeft = [...short].filter((x) => !reviewed.has(x)).length;
  const ready = reviewed.size >= data.qc.required_sample && shortLeft === 0;
  const toggle = (set: Set<string>, id: string) => { const n = new Set(set); if (n.has(id)) n.delete(id); else n.add(id); return n; };
  return (
    <div className="space-y-3">
      <p className="font-semibold">QC: reviewed {reviewed.size} of required {data.qc.required_sample}{short.size ? ` · short clips left ${shortLeft}` : ""}</p>
      <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {data.clips.map((c) => (
          <li key={c.id} className="rounded-btn border border-marble-200 p-2">
            <p className="flex items-center justify-between text-small"><span>{c.position}. {c.code} {c.short && <Badge tone="red">short</Badge>}</span>
              <Badge tone={statusTone(c.qc_status)}>{c.qc_status}</Badge></p>
            {c.url && <video src={c.url} poster={c.poster ?? undefined} controls playsInline preload="none" className="mt-1 w-full rounded-btn"
              onPlay={() => setReviewed((s) => new Set(s).add(c.id))} />}
            {c.qc_status === "pending" && c.url && (
              <div className="mt-1 flex gap-3 text-small">
                <label className="flex items-center gap-1"><input type="checkbox" checked={reviewed.has(c.id)} onChange={() => setReviewed((s) => toggle(s, c.id))} /> reviewed</label>
                <label className="flex items-center gap-1"><input type="checkbox" checked={rejected.has(c.id)} onChange={() => setRejected((s) => toggle(s, c.id))} /> reject</label>
              </div>
            )}
          </li>
        ))}
      </ul>
      {view}
      <button className="pp-btn pp-btn-primary" disabled={!pending.length || !ready || busy}
        onClick={() => run(async () => {
          const r = await api(`/admin/events/${eventId}/qc-approve`, { method: "POST", json: { reviewed_ids: [...reviewed], rejected_ids: [...rejected] } });
          onDone();
          return r;
        }, "Batch approved: proof videos are being sent on WhatsApp.")}>
        Approve batch ({pending.length - rejected.size} clips)
      </button>
    </div>
  );
}

function Disrupt({ eventId, status, onDone }: { eventId: number; status: string; onDone: () => void }) {
  const [date, setDate] = useState("");
  const { run, busy, view } = useAction();
  if (!["scheduled", "started"].includes(status)) return null;
  return (
    <Card title="Event disrupted?">
      <p className="mb-3 text-small text-ink-600">Reschedule: every devotee gets Accept / Refund buttons; no reply in 48 hours means accept. Or refund everyone.</p>
      {view}
      <div className="flex flex-wrap items-end gap-3">
        <Field label="New date and time (IST)"><input type="datetime-local" className="pp-input" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <button className="pp-btn pp-btn-secondary" disabled={!date || busy} onClick={() => window.confirm("Reschedule all bookings to the new date?") &&
          run(async () => { await api(`/admin/events/${eventId}/disrupt`, { method: "POST", json: { action: "reschedule", new_starts_at: date } }); onDone(); }, "Rescheduled; devotees notified.")}>
          Reschedule
        </button>
        <button className="pp-btn border border-sindoor-600 text-sindoor-600" disabled={busy} onClick={() => window.confirm("Cancel the event and refund every booking?") &&
          run(async () => { await api(`/admin/events/${eventId}/disrupt`, { method: "POST", json: { action: "refund" } }); onDone(); }, "Event cancelled; refunds issued.")}>
          Refund all
        </button>
      </div>
    </Card>
  );
}
