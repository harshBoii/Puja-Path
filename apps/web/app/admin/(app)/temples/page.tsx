"use client";
import { useState } from "react";

import { Badge, Card, Field, PageTitle, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

const LOCALES = ["en", "hi", "ta", "te"] as const;
type Temple = { id: number; slug: string; name: string; city: string; state: string; lat: number | null; lng: number | null;
  presiding_deity: string; venue_type: string; photos: { key: string; alt: Record<string, string>; taken_on: string }[];
  translations: { locale: string; name: string; address: string | null; history_md: string | null }[] };

const blank = (): Temple => ({ id: 0, slug: "", name: "", city: "", state: "", lat: null, lng: null, presiding_deity: "", venue_type: "temple",
  photos: [], translations: [] });

/** venue_type is required: it shows on every card and page, so a yagashala is never called a temple (PRD §12). */
export default function Temples() {
  const { data, reload } = useApi<Temple[]>("/admin/temples");
  const [edit, setEdit] = useState<Temple | null>(null);
  const { run, busy, view } = useAction();
  const save = (t: Temple) => run(async () => {
    const body = { slug: t.slug || null, city: t.city, state: t.state, lat: t.lat, lng: t.lng, presiding_deity: t.presiding_deity,
      venue_type: t.venue_type, photos: t.photos, translations: t.translations.filter((x) => x.name.trim()) };
    await api(t.id ? `/admin/temples/${t.id}` : "/admin/temples", { method: t.id ? "PUT" : "POST", json: body });
    setEdit(null);
    reload();
  }, "Temple saved.");
  const tr = (t: Temple, l: string) => t.translations.find((x) => x.locale === l) ?? { locale: l, name: "", address: "", history_md: "" };
  const setTr = (t: Temple, l: string, patch: Partial<Temple["translations"][number]>) =>
    setEdit({ ...t, translations: [...t.translations.filter((x) => x.locale !== l), { ...tr(t, l), ...patch }] });
  return (
    <>
      <PageTitle actions={<button className="pp-btn pp-btn-primary" onClick={() => setEdit(blank())}>New temple</button>}>Temples</PageTitle>
      {view}
      {edit && (
        <Card title={edit.id ? `Edit ${edit.name}` : "New temple"}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="City"><input className="pp-input" value={edit.city} onChange={(e) => setEdit({ ...edit, city: e.target.value })} /></Field>
            <Field label="State"><input className="pp-input" value={edit.state} onChange={(e) => setEdit({ ...edit, state: e.target.value })} /></Field>
            <Field label="Venue type"><select className="pp-input" value={edit.venue_type} onChange={(e) => setEdit({ ...edit, venue_type: e.target.value })}>
              {["temple", "yagashala", "ghat", "kund"].map((v) => <option key={v}>{v}</option>)}</select></Field>
            <Field label="Presiding deity"><input className="pp-input" value={edit.presiding_deity} onChange={(e) => setEdit({ ...edit, presiding_deity: e.target.value })} /></Field>
            <Field label="Latitude"><input type="number" step="any" className="pp-input" value={edit.lat ?? ""} onChange={(e) => setEdit({ ...edit, lat: e.target.value ? Number(e.target.value) : null })} /></Field>
            <Field label="Longitude"><input type="number" step="any" className="pp-input" value={edit.lng ?? ""} onChange={(e) => setEdit({ ...edit, lng: e.target.value ? Number(e.target.value) : null })} /></Field>
          </div>
          {LOCALES.map((l) => (
            <fieldset key={l} lang={l} className="mt-3 grid gap-2 rounded-btn border border-marble-200 p-3 sm:grid-cols-3">
              <legend className="px-1 font-semibold">{l}</legend>
              <input className="pp-input" placeholder="Name" value={tr(edit, l).name} onChange={(e) => setTr(edit, l, { name: e.target.value })} />
              <input className="pp-input" placeholder="Address" value={tr(edit, l).address ?? ""} onChange={(e) => setTr(edit, l, { address: e.target.value })} />
              <textarea className="pp-input" placeholder="Short history" value={tr(edit, l).history_md ?? ""} onChange={(e) => setTr(edit, l, { history_md: e.target.value })} />
            </fieldset>
          ))}
          <p className="mt-2 text-small text-ink-600">Temple photos come from the Media library (each needs the temple and date taken).</p>
          <div className="mt-3 flex gap-2">
            <button className="pp-btn pp-btn-primary" disabled={busy} onClick={() => save(edit)}>Save</button>
            <button className="pp-btn pp-btn-secondary" onClick={() => setEdit(null)}>Cancel</button>
          </div>
        </Card>
      )}
      <ul className="grid gap-3 md:grid-cols-2">
        {(data ?? []).map((t) => (
          <li key={t.id} className="pp-card flex items-center justify-between gap-3 p-4">
            <span><span className="font-semibold">{t.name}</span> <span className="text-small text-ink-600">{t.city} · </span><Badge>{t.venue_type}</Badge>
              <span className="ml-2 text-small text-ink-600">{t.translations.map((x) => x.locale).join(", ")}</span></span>
            <button className="pp-link" onClick={() => setEdit(t)}>Edit</button>
          </li>
        ))}
      </ul>
    </>
  );
}
