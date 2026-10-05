"use client";
import { cx } from "@pujapath/ui";
import Link from "next/link";
import { use, useEffect, useState } from "react";

import { Badge, Card, Field, PageTitle, statusTone, useAction, useApi } from "@/components/admin/ui";
import { resumableUpload } from "@/components/admin/upload";
import { api } from "@/lib/client";

const LOCALES = ["en", "hi", "ta", "te"] as const;
type L = (typeof LOCALES)[number];
type Tr = { title: string; subtitle: string | null; occasion_chip: string | null; about_md: string | null;
  benefits: { title: string; line: string }[]; rituals: { title: string; text: string; main?: boolean }[]; faqs: { q: string; a: string }[];
  meta_title: string | null; meta_description: string | null; published?: boolean };
type Puja = {
  id: number; temple_id: number; kind: string; slug: string; status: string; deity_tags: string[]; dosha_tags: string[]; benefit_tags: string[];
  tradition: string; duration_minutes: number; priests_count: number; sankalp_language: string; requires_nakshatra: boolean;
  video_sla_hours: number | null; deliverables: string[]; prasad_box: string[] | null; images: { key: string; alt: Record<string, string> }[];
  translations: Partial<Record<L, Tr>>;
  packages: { code: string; max_names: number; price_inr_minor: number; price_usd_minor: number; active: boolean }[];
  addons: { id: number; image_key: string | null; price_inr_minor: number; price_usd_minor: number; max_qty: number; ships_home: boolean;
    active: boolean; translations: Record<string, { name: string; description: string | null }> }[];
  seva_plan: { rrule: string; occurrences: number; autopay_allowed: boolean } | null;
};
type Err = { locale: string | null; field: string; code: string };

const emptyTr = (): Tr => ({ title: "", subtitle: "", occasion_chip: "", about_md: "", benefits: [], rituals: [], faqs: [],
  meta_title: "", meta_description: "" });
const csv = (a: string[] | null | undefined) => (a ?? []).join(", ");
const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export default function PujaEditor({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, reload, setData } = useApi<Puja>(`/admin/pujas/${id}`);
  const temples = useApi<{ id: number; name: string }[]>("/admin/temples");
  const [tab, setTab] = useState<L>("en");
  const [errors, setErrors] = useState<Err[]>([]);
  const [previewKey, setPreviewKey] = useState(0);
  const { run, busy, view } = useAction();
  if (!data) return <p>Loading…</p>;
  const p = data;
  const set = (patch: Partial<Puja>) => setData({ ...p, ...patch });

  const saveBase = () => run(async () => {
    setData(await api<Puja>(`/admin/pujas/${id}`, { method: "PUT", json: {
      temple_id: p.temple_id, kind: p.kind, slug: p.slug, deity_tags: p.deity_tags, dosha_tags: p.dosha_tags, benefit_tags: p.benefit_tags,
      tradition: p.tradition, duration_minutes: p.duration_minutes, priests_count: p.priests_count, sankalp_language: p.sankalp_language,
      requires_nakshatra: p.requires_nakshatra, video_sla_hours: p.video_sla_hours, deliverables: p.deliverables, prasad_box: p.prasad_box,
      images: p.images } }));
    setPreviewKey((k) => k + 1);
  }, "Saved.");
  const publish = (locales: L[]) => run(async () => {
    const v = await api<{ errors: Err[] }>(`/admin/pujas/${id}/validate`, { method: "POST", json: { locales } });
    setErrors(v.errors);
    if (v.errors.length) throw new Error(`Publishing blocked: ${v.errors.length} problem(s) listed below.`);
    await api(`/admin/pujas/${id}/publish`, { method: "POST", json: { locales } });
    reload();
  }, `Published ${locales.join(", ")}. Live pages revalidated.`);

  return (
    <>
      <PageTitle actions={<>
        <Badge tone={statusTone(p.status)}>{p.status}</Badge>
        <Link href={`/admin/events?puja_id=${p.id}`} className="pp-btn pp-btn-secondary min-h-10">Events</Link>
      </>}>{p.translations.en?.title || p.slug}</PageTitle>
      {view}
      {errors.length > 0 && (
        <Card title="Publish blocked" className="border border-sindoor-600">
          <ul className="list-disc pl-5 text-sindoor-600">{errors.map((e, i) => <li key={i}>{e.locale ? `[${e.locale}] ` : ""}{e.field}: {e.code}</li>)}</ul>
        </Card>
      )}

      <Card title="Facts (required, no defaults)" actions={<button className="pp-btn pp-btn-primary min-h-10" disabled={busy} onClick={saveBase}>Save</button>}>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Temple"><select className="pp-input" value={p.temple_id} onChange={(e) => set({ temple_id: Number(e.target.value) })}>
            {(temples.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
          <Field label="Slug"><input className="pp-input" value={p.slug} onChange={(e) => set({ slug: e.target.value })} /></Field>
          <Field label="Tradition"><input className="pp-input" value={p.tradition} onChange={(e) => set({ tradition: e.target.value })} /></Field>
          <Field label="Duration (minutes)"><input type="number" className="pp-input" value={p.duration_minutes || ""} onChange={(e) => set({ duration_minutes: Number(e.target.value) })} /></Field>
          <Field label="Number of priests"><input type="number" className="pp-input" value={p.priests_count || ""} onChange={(e) => set({ priests_count: Number(e.target.value) })} /></Field>
          <Field label="Sankalp language"><input className="pp-input" value={p.sankalp_language} onChange={(e) => set({ sankalp_language: e.target.value })} /></Field>
          <Field label="Video SLA hours" hint="Empty = site default"><input type="number" className="pp-input" value={p.video_sla_hours ?? ""}
            onChange={(e) => set({ video_sla_hours: e.target.value ? Number(e.target.value) : null })} /></Field>
          <Field label="Deity tags"><input className="pp-input" defaultValue={csv(p.deity_tags)} onBlur={(e) => set({ deity_tags: list(e.target.value) })} /></Field>
          <Field label="Dosha tags"><input className="pp-input" defaultValue={csv(p.dosha_tags)} onBlur={(e) => set({ dosha_tags: list(e.target.value) })} /></Field>
          <Field label="Purpose tags"><input className="pp-input" defaultValue={csv(p.benefit_tags)} onBlur={(e) => set({ benefit_tags: list(e.target.value) })} /></Field>
          <Field label="Deliverables" hint="sankalp_clip, full_video, photos"><input className="pp-input" defaultValue={csv(p.deliverables)} onBlur={(e) => set({ deliverables: list(e.target.value) })} /></Field>
          <Field label="Prasad box" hint="shelf-stable only: dry_prasad, kumkum, vibhuti, akshata, raksha_sutra"><input className="pp-input" defaultValue={csv(p.prasad_box)}
            onBlur={(e) => set({ prasad_box: list(e.target.value).length ? list(e.target.value) : null })} /></Field>
          <label className="flex items-center gap-2"><input type="checkbox" checked={p.requires_nakshatra} onChange={(e) => set({ requires_nakshatra: e.target.checked })} /> Requires nakshatra</label>
        </div>
      </Card>

      <Images puja={p} set={set} />
      <Packages puja={p} onSaved={reload} />
      {p.kind === "seva" && <SevaPlan puja={p} onSaved={reload} />}
      <Addons puja={p} onSaved={reload} />

      <Card title="Translations" actions={<button className="pp-btn pp-btn-primary min-h-10" disabled={busy}
        onClick={() => publish(LOCALES.filter((l) => p.translations[l]))}>Publish all saved locales</button>}>
        <div className="mb-3 flex gap-2" role="tablist">
          {LOCALES.map((l) => (
            <button key={l} role="tab" aria-selected={tab === l} className="pp-chip" data-selected={tab === l} onClick={() => setTab(l)}>
              {l} {p.translations[l]?.published ? "●" : p.translations[l] ? "○" : "+"}
            </button>
          ))}
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <TranslationForm key={`${tab}-${previewKey}`} pujaId={p.id} locale={tab} initial={p.translations[tab] ?? emptyTr()}
            onSaved={(np) => { setData(np); setPreviewKey((k) => k + 1); }} onPublish={() => publish([tab])} />
          <div>
            <p className="mb-1 text-small text-ink-600">Live preview ({tab}) — the real page, including unpublished copy</p>
            {p.translations[tab] ? (
              <iframe key={previewKey} title={`Preview ${tab}`} src={`/${tab}/preview/${p.id}`}
                className="h-[720px] w-full rounded-card border border-marble-200 bg-surface" />
            ) : <p className="text-ink-600">Save this locale to see the preview.</p>}
          </div>
        </div>
      </Card>
    </>
  );
}

function TranslationForm({ pujaId, locale, initial, onSaved, onPublish }: {
  pujaId: number; locale: L; initial: Tr; onSaved: (p: Puja) => void; onPublish: () => void;
}) {
  const [tr, setTr] = useState<Tr>(initial);
  const { run, busy, view } = useAction();
  const up = (patch: Partial<Tr>) => setTr({ ...tr, ...patch });
  return (
    <div className="space-y-3" lang={locale}>
      {view}
      <Field label="Title"><input className="pp-input" value={tr.title} onChange={(e) => up({ title: e.target.value })} /></Field>
      <Field label="Subtitle"><input className="pp-input" value={tr.subtitle ?? ""} onChange={(e) => up({ subtitle: e.target.value })} /></Field>
      <Field label="Occasion chip"><input className="pp-input" value={tr.occasion_chip ?? ""} onChange={(e) => up({ occasion_chip: e.target.value })} /></Field>
      <Field label="About" hint="Traditional purpose only — no promised outcomes."><textarea className="pp-input min-h-32" value={tr.about_md ?? ""} onChange={(e) => up({ about_md: e.target.value })} /></Field>
      <Field label="Meta title"><input className="pp-input" value={tr.meta_title ?? ""} onChange={(e) => up({ meta_title: e.target.value })} /></Field>
      <Field label="Meta description"><textarea className="pp-input" value={tr.meta_description ?? ""} onChange={(e) => up({ meta_description: e.target.value })} /></Field>
      <ListEditor label="Benefits (title | line)" rows={tr.benefits.map((b) => `${b.title} | ${b.line}`)}
        onChange={(rows) => up({ benefits: rows.map((r) => { const [title, line = ""] = r.split("|").map((x) => x.trim()); return { title, line }; }) })} />
      <ListEditor label="Rituals (title | text | main)" rows={tr.rituals.map((r) => `${r.title} | ${r.text}${r.main ? " | main" : ""}`)}
        onChange={(rows) => up({ rituals: rows.map((r) => { const [title, text = "", main] = r.split("|").map((x) => x.trim()); return { title, text, main: main === "main" }; }) })} />
      <ListEditor label="FAQs (question | answer)" rows={tr.faqs.map((f) => `${f.q} | ${f.a}`)}
        onChange={(rows) => up({ faqs: rows.map((r) => { const [q, a = ""] = r.split("|").map((x) => x.trim()); return { q, a }; }) })} />
      <div className="flex gap-2">
        <button className="pp-btn pp-btn-primary" disabled={busy} onClick={() => run(async () => {
          const { published: _published, ...body } = tr;
          void _published;
          onSaved(await api<Puja>(`/admin/pujas/${pujaId}/translations/${locale}`, { method: "PUT", json: body }));
        }, "Saved.")}>Save {locale}</button>
        <button className="pp-btn pp-btn-secondary" disabled={busy} onClick={onPublish}>Publish {locale}</button>
      </div>
    </div>
  );
}

function ListEditor({ label, rows, onChange }: { label: string; rows: string[]; onChange: (rows: string[]) => void }) {
  return (
    <Field label={label} hint="One per line">
      <textarea className="pp-input min-h-28 font-mono text-small" defaultValue={rows.join("\n")}
        onBlur={(e) => onChange(e.target.value.split("\n").map((x) => x.trim()).filter(Boolean))} />
    </Field>
  );
}

function Images({ puja, set }: { puja: Puja; set: (p: Partial<Puja>) => void }) {
  const [pct, setPct] = useState<number | null>(null);
  const [alt, setAlt] = useState<Record<L, string>>({ en: "", hi: "", ta: "", te: "" });
  return (
    <Card title="Images (up to 6, alt text required per locale)">
      <ul className="mb-3 grid gap-3 sm:grid-cols-3">
        {puja.images.map((img, i) => (
          <li key={img.key} className="rounded-btn border border-marble-200 p-2 text-small">
            <img src={img.key.startsWith("/") ? img.key : `/media/${img.key}`} alt={img.alt.en ?? ""} className="mb-1 aspect-[4/3] w-full rounded-btn object-cover" />
            {LOCALES.map((l) => (
              <input key={l} lang={l} className="pp-input mb-1 min-h-9 py-1 text-small" placeholder={`alt (${l})`} value={img.alt[l] ?? ""}
                onChange={(e) => set({ images: puja.images.map((x, k) => (k === i ? { ...x, alt: { ...x.alt, [l]: e.target.value } } : x)) })} />
            ))}
            <button className="pp-link" onClick={() => set({ images: puja.images.filter((_, k) => k !== i) })}>Remove</button>
          </li>
        ))}
      </ul>
      {puja.images.length < 6 && (
        <div className="grid gap-2 sm:grid-cols-5">
          {LOCALES.map((l) => <input key={l} lang={l} className="pp-input" placeholder={`alt (${l})`} value={alt[l]} onChange={(e) => setAlt({ ...alt, [l]: e.target.value })} />)}
          <input type="file" accept="image/*" disabled={pct !== null || LOCALES.some((l) => !alt[l].trim())} onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            setPct(0);
            try {
              const r = await resumableUpload(f, { purpose: "image", temple_id: puja.temple_id, alt }, setPct);
              set({ images: [...puja.images, { key: String(r.key), alt }] });
              setAlt({ en: "", hi: "", ta: "", te: "" });
            } finally { setPct(null); }
          }} />
        </div>
      )}
      {pct !== null && <progress max={100} value={pct} className="mt-2 w-full" />}
      <p className="mt-2 text-small text-ink-600">Remember to Save the facts card to keep image changes.</p>
    </Card>
  );
}

function Packages({ puja, onSaved }: { puja: Puja; onSaved: () => void }) {
  const base = ["individual", "couple", "family"].map((code, i) => puja.packages.find((p) => p.code === code) ??
    { code, max_names: [1, 2, 4][i], price_inr_minor: 0, price_usd_minor: 0, active: false });
  const [rows, setRows] = useState(base);
  useEffect(() => setRows(base), [puja.packages]); // eslint-disable-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  const { run, busy, view } = useAction();
  return (
    <Card title="Packages (prices set by hand in INR and USD)" actions={<button className="pp-btn pp-btn-primary min-h-10" disabled={busy}
      onClick={() => run(async () => { await api(`/admin/pujas/${puja.id}/packages`, { method: "PUT", json: rows }); onSaved(); }, "Packages saved.")}>Save</button>}>
      {view}
      <div className="grid gap-2">
        {rows.map((r, i) => (
          <div key={r.code} className="grid grid-cols-2 items-end gap-2 sm:grid-cols-5">
            <p className="font-semibold">{r.code}</p>
            <Field label="Names"><input type="number" className="pp-input" value={r.max_names} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, max_names: Number(e.target.value) } : x)))} /></Field>
            <Field label="₹"><input type="number" className="pp-input" value={r.price_inr_minor / 100} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, price_inr_minor: Math.round(Number(e.target.value) * 100) } : x)))} /></Field>
            <Field label="$"><input type="number" className="pp-input" value={r.price_usd_minor / 100} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, price_usd_minor: Math.round(Number(e.target.value) * 100) } : x)))} /></Field>
            <label className="flex items-center gap-2"><input type="checkbox" checked={r.active} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, active: e.target.checked } : x)))} /> active</label>
          </div>
        ))}
      </div>
    </Card>
  );
}

function SevaPlan({ puja, onSaved }: { puja: Puja; onSaved: () => void }) {
  const [plan, setPlan] = useState(puja.seva_plan ?? { rrule: "FREQ=WEEKLY;BYDAY=TU", occurrences: 7, autopay_allowed: true });
  const { run, busy, view } = useAction();
  return (
    <Card title="Seva plan" actions={<button className="pp-btn pp-btn-primary min-h-10" disabled={busy}
      onClick={() => run(async () => { await api(`/admin/pujas/${puja.id}/seva-plan`, { method: "PUT", json: plan }); onSaved(); }, "Seva plan saved.")}>Save</button>}>
      {view}
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Recurrence (RFC 5545 RRULE)"><input className="pp-input" value={plan.rrule} onChange={(e) => setPlan({ ...plan, rrule: e.target.value })} /></Field>
        <Field label="Occurrences"><input type="number" className="pp-input" value={plan.occurrences} onChange={(e) => setPlan({ ...plan, occurrences: Number(e.target.value) })} /></Field>
        <label className="flex items-center gap-2"><input type="checkbox" checked={plan.autopay_allowed} onChange={(e) => setPlan({ ...plan, autopay_allowed: e.target.checked })} /> UPI AutoPay allowed</label>
      </div>
    </Card>
  );
}

function Addons({ puja, onSaved }: { puja: Puja; onSaved: () => void }) {
  const [rows, setRows] = useState(puja.addons);
  const { run, busy, view } = useAction();
  const blank = { id: 0, image_key: null, price_inr_minor: 0, price_usd_minor: 0, max_qty: 1, ships_home: false, active: true,
    translations: { en: { name: "", description: null } } } as Puja["addons"][number];
  return (
    <Card title="Chadhava add-ons" actions={<button className="pp-btn pp-btn-primary min-h-10" disabled={busy}
      onClick={() => run(async () => { await api(`/admin/pujas/${puja.id}/addons`, { method: "PUT", json: rows.map((r) => ({ ...r, id: r.id || null })) }); onSaved(); }, "Add-ons saved.")}>Save</button>}>
      {view}
      {rows.map((a, i) => (
        <div key={i} className={cx("mb-3 grid gap-2 rounded-btn border border-marble-200 p-2 sm:grid-cols-4", !a.active && "opacity-60")}>
          {LOCALES.map((l) => (
            <input key={l} lang={l} className="pp-input" placeholder={`name (${l})`} value={a.translations[l]?.name ?? ""}
              onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, translations: { ...x.translations, [l]: { name: e.target.value, description: null } } } : x)))} />
          ))}
          <input type="number" className="pp-input" placeholder="₹" value={a.price_inr_minor / 100} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, price_inr_minor: Math.round(Number(e.target.value) * 100) } : x)))} aria-label="Price INR" />
          <input type="number" className="pp-input" placeholder="$" value={a.price_usd_minor / 100} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, price_usd_minor: Math.round(Number(e.target.value) * 100) } : x)))} aria-label="Price USD" />
          <input type="number" className="pp-input" value={a.max_qty} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, max_qty: Number(e.target.value) } : x)))} aria-label="Max quantity" />
          <div className="flex items-center gap-3 text-small">
            <label className="flex items-center gap-1"><input type="checkbox" checked={a.ships_home} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, ships_home: e.target.checked } : x)))} /> ships home</label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={a.active} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, active: e.target.checked } : x)))} /> active</label>
          </div>
        </div>
      ))}
      <button className="pp-link" onClick={() => setRows([...rows, blank])}>+ add item</button>
    </Card>
  );
}
