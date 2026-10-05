"use client";
import { useState } from "react";

import { Card, Field, PageTitle, useAction, useApi } from "@/components/admin/ui";
import { resumableUpload } from "@/components/admin/upload";
import { api } from "@/lib/client";

const LOCALES = ["en", "hi", "ta", "te"] as const;
type M = { id: number; url: string; temple_id: number | null; taken_on: string | null; alt: Record<string, string>; in_gallery: boolean };

/** Every image needs alt text per locale; gallery images also need the temple and the date taken (PRD §12). */
export default function Media() {
  const { data, reload } = useApi<M[]>("/admin/media");
  const temples = useApi<{ id: number; name: string }[]>("/admin/temples");
  const [alt, setAlt] = useState<Record<string, string>>({ en: "", hi: "", ta: "", te: "" });
  const [templeId, setTempleId] = useState<number | null>(null);
  const [taken, setTaken] = useState("");
  const [gallery, setGallery] = useState(false);
  const [pct, setPct] = useState<number | null>(null);
  const { run, view } = useAction();
  const ready = LOCALES.every((l) => alt[l].trim()) && (!gallery || (templeId && taken));
  return (
    <>
      <PageTitle>Media</PageTitle>
      {view}
      <Card title="Upload image">
        <div className="grid gap-2 sm:grid-cols-4">
          {LOCALES.map((l) => <Field key={l} label={`Alt (${l})`}><input lang={l} className="pp-input" value={alt[l]} onChange={(e) => setAlt({ ...alt, [l]: e.target.value })} /></Field>)}
          <Field label="Temple"><select className="pp-input" value={templeId ?? ""} onChange={(e) => setTempleId(Number(e.target.value) || null)}>
            <option value="">—</option>{(temples.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
          <Field label="Date taken"><input type="date" className="pp-input" value={taken} onChange={(e) => setTaken(e.target.value)} /></Field>
          <label className="flex items-center gap-2"><input type="checkbox" checked={gallery} onChange={(e) => setGallery(e.target.checked)} /> Show in home gallery</label>
          <input type="file" accept="image/*" disabled={!ready || pct !== null} onChange={(e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            setPct(0);
            run(async () => {
              await resumableUpload(f, { purpose: "image", alt, temple_id: templeId ?? undefined, taken_on: taken || undefined, in_gallery: gallery }, setPct);
              reload();
            }, "Uploaded and resized.").finally(() => setPct(null));
          }} />
        </div>
        {pct !== null && <progress max={100} value={pct} className="mt-2 w-full" />}
      </Card>
      <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {(data ?? []).map((m) => (
          <li key={m.id} className="pp-card overflow-hidden text-small">
            <img src={m.url} alt={m.alt.en ?? ""} className="aspect-square w-full object-cover" loading="lazy" />
            <div className="p-2">
              <p className="truncate">{m.alt.en}</p>
              <p className="text-ink-600">{m.taken_on ?? "no date"}</p>
              <label className="flex items-center gap-1"><input type="checkbox" checked={m.in_gallery}
                onChange={(e) => run(async () => { await api(`/admin/media/${m.id}`, { method: "PATCH", json: { in_gallery: e.target.checked } }); reload(); })} /> gallery</label>
              <button className="pp-link" onClick={() => navigator.clipboard.writeText(m.url)}>Copy URL</button>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
