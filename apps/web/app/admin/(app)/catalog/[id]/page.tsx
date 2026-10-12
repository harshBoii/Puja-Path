"use client";
// Puja editor as a step-by-step form. Every step stays mounted (only the current one is shown), so unsaved edits
// survive jumping between steps; "Save & continue" saves whatever the current step registered via useSaver.
import { DiyaLoader, cx } from "@pujapath/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, use, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { EventsManager } from "@/components/admin/EventsManager";
import { Badge, Card, Field, PageTitle, statusTone, useAction, useApi } from "@/components/admin/ui";
import { resumableUpload } from "@/components/admin/upload";
import { api } from "@/lib/client";

const LOCALES = ["en", "hi", "ta", "te"] as const;
type L = (typeof LOCALES)[number];
const LANG: Record<L, string> = { en: "English", hi: "Hindi", ta: "Tamil", te: "Telugu" };
type Ritual = { title: string; text: string; main?: boolean };
type Tr = { title: string; subtitle: string | null; occasion_chip: string | null; about_md: string | null;
  benefits: { title: string; line: string }[]; rituals: Ritual[]; faqs: { q: string; a: string }[];
  meta_title: string | null; meta_description: string | null; published?: boolean };
type Img = { key: string; alt: Record<string, string>; url?: string | null; width?: number | null };
type Puja = {
  id: number; temple_id: number; kind: string; slug: string; status: string; deity_tags: string[]; dosha_tags: string[]; benefit_tags: string[];
  tradition: string; duration_minutes: number; priests_count: number; sankalp_language: string; requires_nakshatra: boolean;
  video_sla_hours: number | null; deliverables: string[]; prasad_box: string[] | null; images: Img[];
  translations: Partial<Record<L, Tr>>;
  packages: { code: string; max_names: number; price_inr_minor: number; price_usd_minor: number; active: boolean }[];
  addons: { id: number; image_key: string | null; image_url?: string | null; price_inr_minor: number; price_usd_minor: number; max_qty: number;
    ships_home: boolean; active: boolean; translations: Record<string, { name: string; description: string | null }> }[];
  seva_plan: { rrule: string; occurrences: number; autopay_allowed: boolean } | null;
};
type Err = { locale: string | null; field: string; code: string };

const STEPS = [
  { id: "basics", label: "Basics" },
  { id: "content", label: "Page content" },
  { id: "photos", label: "Photos" },
  { id: "pricing", label: "Prices & items" },
  { id: "dates", label: "Dates" },
  { id: "advanced", label: "Advanced", optional: true },
  { id: "publish", label: "Review & publish" },
] as const;
type Step = (typeof STEPS)[number]["id"];

const DELIVERABLES: [string, string][] = [["sankalp_clip", "Personal sankalp clip"], ["full_video", "Full ritual video"], ["photos", "Photos"]];
const PRASAD: [string, string][] = [["dry_prasad", "Dry prasad"], ["kumkum", "Kumkum"], ["vibhuti", "Vibhuti"], ["akshata", "Akshata"],
  ["raksha_sutra", "Raksha sutra"]];
const KIND: Record<string, string> = { one_time: "One-time puja", seva: "Seva (recurring)", chadhava: "Chadhava" };

const emptyTr = (): Tr => ({ title: "", subtitle: "", occasion_chip: "", about_md: "", benefits: [], rituals: [], faqs: [],
  meta_title: "", meta_description: "" });
const csv = (a: string[] | null | undefined) => (a ?? []).join(", ");
/** Prefer the URL the API resolved (R2 or /media); fall back to the stored key. */
const mediaSrc = (key: string, url?: string | null) => url || (/^(https?:)?\/\//.test(key) || key.startsWith("/") ? key : `/media/${key}`);
const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
const toggle = (a: string[], v: string, on: boolean) => (on ? [...new Set([...a, v])] : a.filter((x) => x !== v));

// ------------------------------------------------------------------ step savers
type Saver = () => Promise<void>;
const SaverCtx = createContext<(id: string, fn: Saver | null) => void>(() => {});
/** Site config inr_per_usd; null while loading. */
const RateCtx = createContext<number | null>(null);

/** Registers what "Save & continue" must save for `step`. */
function useSaver(step: Step, name: string, fn: Saver) {
  const register = useContext(SaverCtx);
  const ref = useRef(fn);
  useEffect(() => { ref.current = fn; });
  useEffect(() => {
    register(`${step}:${name}`, () => ref.current());
    return () => register(`${step}:${name}`, null);
  }, [register, step, name]);
}

export default function PujaEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, reload, setData } = useApi<Puja>(`/admin/pujas/${id}`);
  if (!data) return <DiyaLoader label="Loading…" />;
  return <PujaEditor p={data} setP={setData} reload={reload} />;
}

function PujaEditor({ p, setP, reload }: { p: Puja; setP: (p: Puja) => void; reload: () => void }) {
  const [step, setStep] = useState<Step>("basics");
  const [locale, setLocale] = useState<L>("en");
  const [drafts, setDrafts] = useState<Record<L, Tr>>(() =>
    Object.fromEntries(LOCALES.map((l) => [l, p.translations[l] ?? emptyTr()])) as Record<L, Tr>);
  const [dirty, setDirty] = useState<L[]>([]);
  const [errors, setErrors] = useState<Err[] | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const savers = useRef(new Map<string, Saver>());
  const register = useCallback((key: string, fn: Saver | null) => { if (fn) savers.current.set(key, fn); else savers.current.delete(key); }, []);
  const { run, busy, view } = useAction();
  const rate = useApi<{ inr_per_usd: number }>("/admin/price-rate");
  const events = useApi<{ status: string; booking_cutoff_at: string }[]>(`/admin/events?puja_id=${p.id}`);
  const [now] = useState(() => Date.now());
  const openDates = events.data?.filter((e) => e.status === "scheduled" && new Date(e.booking_cutoff_at).getTime() > now).length ?? null;
  const set = (patch: Partial<Puja>) => setP({ ...p, ...patch });
  const edit = (l: L, patch: Partial<Tr>) => {
    setDrafts((d) => ({ ...d, [l]: { ...d[l], ...patch } }));
    setDirty((d) => (d.includes(l) ? d : [...d, l]));
  };

  const saveBase = async () => {
    setP(await api<Puja>(`/admin/pujas/${p.id}`, { method: "PUT", json: {
      temple_id: p.temple_id, kind: p.kind, slug: p.slug, deity_tags: p.deity_tags, dosha_tags: p.dosha_tags, benefit_tags: p.benefit_tags,
      tradition: p.tradition, duration_minutes: p.duration_minutes, priests_count: p.priests_count, sankalp_language: p.sankalp_language,
      requires_nakshatra: p.requires_nakshatra, video_sla_hours: p.video_sla_hours, deliverables: p.deliverables, prasad_box: p.prasad_box,
      images: p.images.map(({ url: _url, ...img }) => { void _url; return img; }) } }));
    setPreviewKey((k) => k + 1);
  };
  const saveCopy = async () => {
    let latest: Puja | null = null;
    for (const l of dirty) {
      const { published: _published, ...body } = drafts[l];
      void _published;
      latest = await api<Puja>(`/admin/pujas/${p.id}/translations/${l}`, { method: "PUT", json: {
        ...body,
        benefits: body.benefits.filter((b) => b.title.trim() || b.line.trim()),
        rituals: body.rituals.filter((r) => r.title.trim() || r.text.trim()),
        faqs: body.faqs.filter((f) => f.q.trim() || f.a.trim()),
      } });
    }
    if (latest) { setP(latest); setPreviewKey((k) => k + 1); }
    setDirty([]);
  };

  const validate = () => run(async () => {
    const saved = LOCALES.filter((l) => p.translations[l]);
    setErrors((await api<{ errors: Err[] }>(`/admin/pujas/${p.id}/validate`, { method: "POST", json: { locales: saved.length ? saved : ["en"] } })).errors);
  }, "Checked.");
  const goTo = (s: Step) => {
    setStep(s);
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (s === "publish") { validate(); events.reload(); }
  };
  const idx = STEPS.findIndex((s) => s.id === step);
  const next = STEPS[idx + 1]?.id;
  const saveStep = (then?: Step) => run(async () => {
    for (const [key, fn] of savers.current) if (key.startsWith(`${step}:`)) await fn();
    if (then) goTo(then);
  }, "Saved.");

  const done: Partial<Record<Step, boolean>> = {
    basics: !!(p.tradition && p.sankalp_language && p.duration_minutes && p.priests_count && p.deliverables.length),
    content: !!p.translations.en?.title,
    photos: p.images.length > 0,
    pricing: p.packages.some((k) => k.active && k.price_inr_minor > 0 && k.price_usd_minor > 0),
    dates: !!openDates,
  };
  const hasSaver = step !== "dates" && step !== "publish";

  return (
    <SaverCtx.Provider value={register}><RateCtx.Provider value={rate.data?.inr_per_usd ?? null}>
      <PageTitle actions={<>
        <Badge tone={statusTone(p.status)}>{p.status}</Badge>
        <Badge tone="grey">{KIND[p.kind] ?? p.kind}</Badge>
      </>}>{p.translations.en?.title || "Untitled puja"}</PageTitle>

      <nav aria-label="Steps" className="pp-scroll-x mb-5">
        <ol className="flex min-w-max gap-2">
          {STEPS.map((s, i) => (
            <li key={s.id}>
              <button type="button" onClick={() => goTo(s.id)} aria-current={step === s.id ? "step" : undefined}
                className={cx("flex min-h-11 items-center gap-2 rounded-chip border px-3 py-1.5 text-small",
                  step === s.id ? "border-gold-600 bg-gold-100 font-semibold text-ink-900" : "border-marble-200 bg-surface text-ink-600")}>
                <span className={cx("flex h-6 w-6 items-center justify-center rounded-full border text-[0.75rem]",
                  done[s.id] ? "border-tulsi-600 bg-tulsi-600 text-white" : s.id === "dates" && openDates === 0
                    ? "border-sindoor-600 bg-sindoor-600 text-white" : "border-gold-600 text-gold-700")}
                  title={s.id === "dates" && openDates === 0 ? "No dates open for booking" : undefined}>
                  {done[s.id] ? "✓" : s.id === "dates" && openDates === 0 ? "!" : i + 1}</span>
                {s.label}{"optional" in s && <span className="text-ink-600">(optional)</span>}
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <div hidden={step !== "basics"}><BasicsStep p={p} set={set} onSave={saveBase} /></div>
      <div hidden={step !== "content"}>
        <ContentStep p={p} drafts={drafts} dirty={dirty} edit={edit} locale={locale} setLocale={setLocale} previewKey={previewKey} onSave={saveCopy} />
      </div>
      <div hidden={step !== "photos"}><PhotosStep p={p} set={set} onSave={saveBase} /></div>
      <div hidden={step !== "pricing"}>
        <Packages puja={p} onSaved={reload} />
        {p.kind === "seva" && <SevaPlan puja={p} onSaved={reload} />}
        <Addons puja={p} onSaved={setP} />
      </div>
      <div hidden={step !== "dates"}>
        <Card title="Dates" actions={<Link href={`/admin/events?puja_id=${p.id}`} className="pp-link">All events</Link>}>
          <p className="mb-3 text-small text-ink-600">Add the dates this puja will be performed. Devotees can only book a date listed here.</p>
          {openDates === 0 && <NoDatesWarning />}
          <EventsManager pujaId={p.id} onChange={events.reload} />
        </Card>
      </div>
      <div hidden={step !== "advanced"}>
        <AdvancedStep p={p} set={set} drafts={drafts} edit={edit} locale={locale} setLocale={setLocale}
          onSave={async () => { await saveBase(); await saveCopy(); }} />
        <DangerZone puja={p} onChanged={reload} />
      </div>
      <div hidden={step !== "publish"}>
        <PublishStep p={p} errors={errors} busy={busy} unsaved={dirty.length > 0} openDates={openDates} onCheck={validate} goTo={goTo} onChanged={() => { reload(); validate(); }} />
      </div>

      <div className="sticky bottom-0 z-10 -mx-4 mt-2 border-t border-marble-200 bg-surface/95 px-4 py-3 backdrop-blur md:-mx-6 md:px-6">
        {view}
        <div className="flex flex-wrap items-center gap-2">
          {idx > 0 && <button type="button" className="pp-btn pp-btn-secondary" disabled={busy} onClick={() => goTo(STEPS[idx - 1].id)}>← Back</button>}
          <span className="flex-1" />
          {step === "advanced" && <button type="button" className="pp-btn pp-btn-secondary" disabled={busy} onClick={() => goTo("publish")}>Skip</button>}
          {hasSaver && <button type="button" className="pp-btn pp-btn-secondary" disabled={busy} onClick={() => saveStep()}>Save</button>}
          {next && (hasSaver
            ? <button type="button" className="pp-btn pp-btn-primary" disabled={busy} onClick={() => saveStep(next)}>Save &amp; continue →</button>
            : <button type="button" className="pp-btn pp-btn-primary" disabled={busy} onClick={() => goTo(next)}>Continue →</button>)}
        </div>
      </div>
    </RateCtx.Provider></SaverCtx.Provider>
  );
}

// ------------------------------------------------------------------ 1. basics
function BasicsStep({ p, set, onSave }: { p: Puja; set: (p: Partial<Puja>) => void; onSave: Saver }) {
  const temples = useApi<{ id: number; name: string }[]>("/admin/temples");
  useSaver("basics", "base", onSave);
  return (
    <Card title="Basics">
      <p className="mb-4 text-small text-ink-600">The facts shown on the puja page. All are required before publishing.</p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Temple"><select className="pp-input" value={p.temple_id} onChange={(e) => set({ temple_id: Number(e.target.value) })}>
          {(temples.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
        <Field label="Tradition" hint="e.g. Shaiva Agama, Vaidika, Smarta"><input className="pp-input" value={p.tradition} onChange={(e) => set({ tradition: e.target.value })} /></Field>
        <Field label="Sankalp language" hint="Language the priest says the names in, e.g. Sanskrit"><input className="pp-input" value={p.sankalp_language}
          onChange={(e) => set({ sankalp_language: e.target.value })} /></Field>
        <Field label="Duration (minutes)"><input type="number" min={1} className="pp-input" value={p.duration_minutes || ""} onChange={(e) => set({ duration_minutes: Number(e.target.value) })} /></Field>
        <Field label="Number of priests"><input type="number" min={1} className="pp-input" value={p.priests_count || ""} onChange={(e) => set({ priests_count: Number(e.target.value) })} /></Field>
      </div>
      <fieldset className="mt-5">
        <legend className="mb-2 text-small font-semibold">What the devotee receives</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {DELIVERABLES.map(([v, label]) => (
            <label key={v} className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={p.deliverables.includes(v)}
              onChange={(e) => set({ deliverables: toggle(p.deliverables, v, e.target.checked) })} /> {label}</label>
          ))}
        </div>
      </fieldset>
      <label className="mt-3 flex min-h-11 items-center gap-2">
        <input type="checkbox" checked={p.requires_nakshatra} onChange={(e) => set({ requires_nakshatra: e.target.checked })} />
        Ask devotees for their nakshatra (birth star) when booking
      </label>
    </Card>
  );
}

// ------------------------------------------------------------------ 2. page content
function LocaleTabs({ p, locale, setLocale, dirty = [] }: { p: Puja; locale: L; setLocale: (l: L) => void; dirty?: L[] }) {
  return (
    <div className="mb-4 flex flex-wrap gap-2" role="tablist">
      {LOCALES.map((l) => {
        const t = p.translations[l];
        const state = dirty.includes(l) ? "unsaved" : t?.published ? "live" : t ? "draft" : "not started";
        return (
          <button key={l} type="button" role="tab" aria-selected={locale === l} className="pp-chip" data-selected={locale === l} onClick={() => setLocale(l)}>
            {LANG[l]} <span className="text-ink-600">· {state}</span>
          </button>
        );
      })}
    </div>
  );
}

function ContentStep({ p, drafts, dirty, edit, locale, setLocale, previewKey, onSave }: {
  p: Puja; drafts: Record<L, Tr>; dirty: L[]; edit: (l: L, patch: Partial<Tr>) => void; locale: L; setLocale: (l: L) => void;
  previewKey: number; onSave: Saver;
}) {
  useSaver("content", "copy", onSave);
  const tr = drafts[locale];
  const up = (patch: Partial<Tr>) => edit(locale, patch);
  const blank = !tr.title && !tr.about_md && !tr.benefits.length && !tr.rituals.length;
  return (
    <Card title="Page content">
      <p className="mb-3 text-small text-ink-600">Write the page in English first, then each language. A language goes live only when you publish it.</p>
      <LocaleTabs p={p} locale={locale} setLocale={setLocale} dirty={dirty} />
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="space-y-4" lang={locale}>
          {locale !== "en" && blank && drafts.en.title && (
            <button type="button" className="pp-btn pp-btn-secondary" onClick={() => up({ ...drafts.en, published: undefined })}>
              Start from the English text (then translate it)
            </button>
          )}
          <Field label="Title" hint="The puja name as devotees will see it."><input className="pp-input" value={tr.title} onChange={(e) => up({ title: e.target.value })} /></Field>
          <Field label="Subtitle" hint="One line under the title, e.g. “Evening worship of Lord Shiva on Trayodashi”."><input className="pp-input"
            value={tr.subtitle ?? ""} onChange={(e) => up({ subtitle: e.target.value })} /></Field>
          <Field label="Occasion tag" hint="A short label shown on the card, e.g. “Pradosham” or “Maha Shivratri”."><input className="pp-input"
            value={tr.occasion_chip ?? ""} onChange={(e) => up({ occasion_chip: e.target.value })} /></Field>
          <Field label="About this puja" hint="Its traditional purpose and meaning. Don't promise outcomes (e.g. “guaranteed”)."><textarea className="pp-input min-h-32"
            value={tr.about_md ?? ""} onChange={(e) => up({ about_md: e.target.value })} /></Field>

          <Rows label="Why devotees offer it" hint="Short points shown as a list. At least one is required."
            items={tr.benefits} onChange={(benefits) => up({ benefits })} blank={{ title: "", line: "" }} addLabel="+ Add a point"
            render={(b, set) => (<>
              <input className="pp-input" placeholder="Heading, e.g. Removes obstacles" aria-label="Heading" value={b.title} onChange={(e) => set({ title: e.target.value })} />
              <input className="pp-input" placeholder="One line explaining it" aria-label="Explanation" value={b.line} onChange={(e) => set({ line: e.target.value })} />
            </>)} />

          <Rows label="Ritual steps" hint="Optional. What the priests do, in order, shown as a numbered timeline. Mark the most important step as the main ritual."
            items={tr.rituals} onChange={(rituals) => up({ rituals })} blank={{ title: "", text: "", main: false }} addLabel="+ Add a step"
            render={(r, set, i) => (<>
              <input className="pp-input" placeholder="Step name, e.g. Rudrabhishekam" aria-label="Step name" value={r.title} onChange={(e) => set({ title: e.target.value })} />
              <textarea className="pp-input min-h-16" placeholder="What happens in this step" aria-label="What happens" value={r.text} onChange={(e) => set({ text: e.target.value })} />
              <label className="flex items-center gap-2 text-small">
                <input type="radio" name={`main-${locale}`} checked={!!r.main}
                  onChange={() => up({ rituals: tr.rituals.map((x, k) => ({ ...x, main: k === i })) })} /> Main ritual
              </label>
            </>)} />

          <Rows label="Questions & answers" hint="Shown in the FAQ section of this puja (site-wide FAQs are added automatically)."
            items={tr.faqs} onChange={(faqs) => up({ faqs })} blank={{ q: "", a: "" }} addLabel="+ Add question"
            render={(f, set, i) => (<>
              <input className="pp-input" placeholder={`Question ${i + 1}`} aria-label="Question" value={f.q} onChange={(e) => set({ q: e.target.value })} />
              <textarea className="pp-input min-h-20" placeholder="Answer" aria-label="Answer" value={f.a} onChange={(e) => set({ a: e.target.value })} />
            </>)} />
        </div>
        <div>
          <p className="mb-1 text-small text-ink-600">Live preview ({LANG[locale]}) — the real page, including unpublished text. Updates when you save.</p>
          {p.translations[locale] ? (
            <iframe key={`${locale}-${previewKey}`} title={`Preview ${locale}`} src={`/${locale}/preview/${p.id}`}
              className="h-[720px] w-full rounded-card border border-marble-200 bg-surface xl:sticky xl:top-4" />
          ) : <p className="rounded-card border border-dashed border-marble-400 p-6 text-ink-600">Save this language to see the preview.</p>}
        </div>
      </div>
    </Card>
  );
}

/** Repeating group of fields (benefits, rituals, FAQs) with add / reorder / remove. */
function Rows<T>({ label, hint, items, onChange, blank, addLabel, render }: {
  label: string; hint: string; items: T[]; onChange: (items: T[]) => void; blank: T; addLabel: string;
  render: (item: T, set: (patch: Partial<T>) => void, i: number) => ReactNode;
}) {
  const move = (i: number, to: number) => { const n = [...items]; const [x] = n.splice(i, 1); n.splice(to, 0, x); onChange(n); };
  return (
    <fieldset>
      <legend className="text-small font-semibold">{label}</legend>
      <p className="mb-2 text-small text-ink-600">{hint}</p>
      <ol className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2 rounded-btn border border-marble-200 p-2">
            <span className="mt-2 w-5 shrink-0 text-center text-small font-semibold text-gold-700">{i + 1}</span>
            <div className="grid flex-1 gap-2">{render(item, (patch) => onChange(items.map((x, k) => (k === i ? { ...x, ...patch } : x))), i)}</div>
            <div className="flex shrink-0 flex-col gap-1">
              <button type="button" className="pp-link px-1" disabled={i === 0} onClick={() => move(i, i - 1)} aria-label="Move up">↑</button>
              <button type="button" className="pp-link px-1" disabled={i === items.length - 1} onClick={() => move(i, i + 1)} aria-label="Move down">↓</button>
              <button type="button" className="pp-link px-1 text-sindoor-600" onClick={() => onChange(items.filter((_, k) => k !== i))} aria-label="Remove">✕</button>
            </div>
          </li>
        ))}
      </ol>
      <button type="button" className="pp-btn pp-btn-secondary mt-2 min-h-10" onClick={() => onChange([...items, { ...blank }])}>{addLabel}</button>
    </fieldset>
  );
}

// ------------------------------------------------------------------ 3. photos
function PhotosStep({ p, set, onSave }: { p: Puja; set: (p: Partial<Puja>) => void; onSave: Saver }) {
  const [pct, setPct] = useState<number | null>(null);
  const [alt, setAlt] = useState<Record<L, string>>({ en: "", hi: "", ta: "", te: "" });
  const [error, setError] = useState<string | null>(null);
  const altRef = useRef<HTMLInputElement>(null);
  useSaver("photos", "images", onSave);
  const move = (i: number, to: number) => {
    const next = [...p.images];
    const [img] = next.splice(i, 1);
    next.splice(to, 0, img);
    set({ images: next });
  };
  const upload = async (f: File) => {
    // Languages left blank reuse the English description.
    const full = Object.fromEntries(LOCALES.map((l) => [l, alt[l].trim() || alt.en.trim()])) as Record<L, string>;
    setPct(0);
    setError(null);
    try {
      const r = await resumableUpload(f, { purpose: "image", temple_id: p.temple_id, alt: full }, setPct);
      set({ images: [...p.images, { key: String(r.key), alt: full, url: r.url ? String(r.url) : null, width: Number(r.width) || null }] });
      setAlt({ en: "", hi: "", ta: "", te: "" });
    } catch (e) {
      setError(`Upload failed: ${e instanceof Error ? e.message : String(e)}. Try again.`);
    } finally { setPct(null); }
  };
  return (
    <Card title="Photos">
      <p className="mb-4 text-small text-ink-600">Up to 6 photos. The first one is the cover shown on cards and at the top of the page.</p>
      {p.images.length > 0 && (
        <ul className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {p.images.map((img, i) => (
            <li key={img.key} className="rounded-btn border border-marble-200 p-2 text-small">
              <div className="relative">
                <img src={mediaSrc(img.key, img.url)} alt={img.alt.en ?? ""} className="mb-2 aspect-[4/3] w-full rounded-btn bg-marble-100 object-cover" />
                {i === 0 && <span className="absolute left-2 top-2"><Badge>Cover</Badge></span>}
              </div>
              <p className="mb-2 line-clamp-2 text-ink-600">{img.alt.en || <span className="text-sindoor-600">No description</span>}</p>
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" className="pp-link" disabled={i === 0} onClick={() => move(i, i - 1)} aria-label="Move earlier">←</button>
                <button type="button" className="pp-link" disabled={i === p.images.length - 1} onClick={() => move(i, i + 1)} aria-label="Move later">→</button>
                {i > 0 && <button type="button" className="pp-link" onClick={() => move(i, 0)}>Make cover</button>}
                <button type="button" className="pp-link text-sindoor-600" onClick={() => set({ images: p.images.filter((_, k) => k !== i) })}>Remove</button>
              </div>
              <details className="mt-2">
                <summary className="cursor-pointer text-ink-600">Edit description</summary>
                {LOCALES.map((l) => (
                  <input key={l} lang={l} className="pp-input mt-1 min-h-9 py-1 text-small" placeholder={LANG[l]} aria-label={`Description (${LANG[l]})`}
                    value={img.alt[l] ?? ""} onChange={(e) => set({ images: p.images.map((x, k) => (k === i ? { ...x, alt: { ...x.alt, [l]: e.target.value } } : x)) })} />
                ))}
              </details>
            </li>
          ))}
        </ul>
      )}
      {p.images.length < 6 ? (
        <div className="rounded-card border border-dashed border-gold-600 p-4">
          <p className="mb-3 font-semibold">Add a photo</p>
          <Field label="Describe the photo (English)" hint="Read aloud to blind users and used by Google, e.g. “Priest offering milk abhishekam to the Shiva lingam”.">
            <input ref={altRef} className="pp-input" value={alt.en} onChange={(e) => { setAlt({ ...alt, en: e.target.value }); setError(null); }} />
          </Field>
          <details className="mt-2 text-small">
            <summary className="cursor-pointer text-ink-600">Description in other languages (optional, English is used if blank)</summary>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {(["hi", "ta", "te"] as const).map((l) => <input key={l} lang={l} className="pp-input" placeholder={LANG[l]} aria-label={`Description (${LANG[l]})`}
                value={alt[l]} onChange={(e) => setAlt({ ...alt, [l]: e.target.value })} />)}
            </div>
          </details>
          <label className={cx("pp-btn pp-btn-primary mt-4 cursor-pointer", pct !== null && "pointer-events-none opacity-60")} aria-disabled={pct !== null}>
            {pct !== null ? `Uploading… ${pct}%` : "Choose photo to upload"}
            <input type="file" accept="image/*" className="sr-only" disabled={pct !== null}
              onClick={(e) => {
                if (alt.en.trim()) return;
                e.preventDefault();
                setError("Describe the photo first, then choose the file.");
                altRef.current?.focus();
              }}
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
          </label>
          {pct !== null && <progress max={100} value={pct} className="mt-2 w-full" />}
          {error && <p role="alert" className="mt-2 text-sindoor-600">{error}</p>}
        </div>
      ) : <p className="text-ink-600">6 photos added. Remove one to add another.</p>}
      <p className="mt-3 text-small text-ink-600">New photos and order changes are kept when you click “Save”.</p>
    </Card>
  );
}

// ------------------------------------------------------------------ 4. prices & items
function Packages({ puja, onSaved }: { puja: Puja; onSaved: () => void }) {
  const base = ["individual", "couple", "family"].map((code, i) => puja.packages.find((p) => p.code === code) ??
    { code, max_names: [1, 2, 4][i], price_inr_minor: 0, price_usd_minor: 0, active: false });
  const [rows, setRows] = useState(base);
  useEffect(() => setRows(base), [puja.packages]); // eslint-disable-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useSaver("pricing", "packages", async () => { await api(`/admin/pujas/${puja.id}/packages`, { method: "PUT", json: rows }); onSaved(); });
  return (
    <Card title="Packages">
      <p className="mb-3 text-small text-ink-600">Turn on the packages you offer and enter a price in rupees or dollars — the other is filled in for you (edit it to override). “Names” is how many people the priest names in the sankalp.</p>
      <div className="grid gap-3">
        {rows.map((r, i) => (
          <div key={r.code} className={cx("grid grid-cols-2 items-end gap-2 rounded-btn border border-marble-200 p-3 sm:grid-cols-[10rem_repeat(3,1fr)]", !r.active && "opacity-70")}>
            <label className="col-span-2 flex min-h-11 items-center gap-2 font-semibold capitalize sm:col-span-1">
              <input type="checkbox" checked={r.active} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, active: e.target.checked } : x)))} /> {r.code}
            </label>
            <Field label="Names"><input type="number" min={1} max={8} className="pp-input" value={r.max_names} onChange={(e) => setRows(rows.map((x, k) => (k === i ? { ...x, max_names: Number(e.target.value) } : x)))} /></Field>
            <PricePair inr={r.price_inr_minor} usd={r.price_usd_minor}
              onChange={(inr, usd) => setRows((rs) => rs.map((x, k) => (k === i ? { ...x, price_inr_minor: inr, price_usd_minor: usd } : x)))} />
          </div>
        ))}
      </div>
    </Card>
  );
}

/** ₹ and $ inputs. Typing one fills the other at the site rate while the other is empty or still auto-filled;
 *  editing the filled one makes it manual. Prices are minor units; conversions round to whole ₹ / $. */
function PricePair({ inr, usd, onChange }: { inr: number; usd: number; onChange: (inr: number, usd: number) => void }) {
  const rate = useContext(RateCtx);
  const [auto, setAuto] = useState<"inr" | "usd" | null>(null);
  const minor = (v: string) => Math.max(0, Math.round(Number(v) * 100));
  const convert = (v: number, to: "inr" | "usd") => (!rate || !v ? 0
    : to === "usd" ? Math.max(100, Math.round(v / 100 / rate) * 100) : Math.round((v / 100) * rate) * 100);
  const edit = (field: "inr" | "usd", v: number) => {
    const other = field === "inr" ? "usd" : "inr";
    const otherVal = field === "inr" ? usd : inr;
    let next = otherVal;
    let nextAuto: typeof auto = auto === field ? null : auto; // typing into an auto-filled field makes it manual
    if (rate && (otherVal === 0 || auto === other)) {
      next = convert(v, other);
      nextAuto = next ? other : null;
    }
    setAuto(nextAuto);
    if (field === "inr") onChange(v, next); else onChange(next, v);
  };
  const hint = (field: "inr" | "usd") => (auto === field && rate ? `Auto at ₹${rate}/$ — edit to override` : undefined);
  return (<>
    <Field label="Price ₹" hint={hint("inr")}><input type="number" min={0} className="pp-input" placeholder="0" value={inr ? inr / 100 : ""}
      onChange={(e) => edit("inr", minor(e.target.value))} /></Field>
    <Field label="Price $" hint={hint("usd")}><input type="number" min={0} step="0.01" className="pp-input" placeholder="0" value={usd ? usd / 100 : ""}
      onChange={(e) => edit("usd", minor(e.target.value))} /></Field>
  </>);
}

function SevaPlan({ puja, onSaved }: { puja: Puja; onSaved: () => void }) {
  const [plan, setPlan] = useState(puja.seva_plan ?? { rrule: "FREQ=WEEKLY;BYDAY=TU", occurrences: 7, autopay_allowed: true });
  useSaver("pricing", "seva", async () => { await api(`/admin/pujas/${puja.id}/seva-plan`, { method: "PUT", json: plan }); onSaved(); });
  return (
    <Card title="Seva plan">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Repeats" hint="RRULE, e.g. FREQ=WEEKLY;BYDAY=TU = every Tuesday"><input className="pp-input" value={plan.rrule} onChange={(e) => setPlan({ ...plan, rrule: e.target.value })} /></Field>
        <Field label="Number of sevas"><input type="number" min={1} max={52} className="pp-input" value={plan.occurrences} onChange={(e) => setPlan({ ...plan, occurrences: Number(e.target.value) })} /></Field>
        <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={plan.autopay_allowed} onChange={(e) => setPlan({ ...plan, autopay_allowed: e.target.checked })} /> UPI AutoPay allowed</label>
      </div>
    </Card>
  );
}

type Addon = Puja["addons"][number];

function Addons({ puja, onSaved }: { puja: Puja; onSaved: (p: Puja) => void }) {
  const [rows, setRows] = useState<Addon[]>(puja.addons);
  const [uploading, setUploading] = useState<number | null>(null);
  useEffect(() => setRows(puja.addons), [puja.addons]); // eslint-disable-line react-hooks/set-state-in-effect -- reset after save
  const { run, view } = useAction();
  useSaver("pricing", "addons", async () => {
    onSaved(await api<Puja>(`/admin/pujas/${puja.id}/addons`, { method: "PUT", json: rows.map((r) => ({ ...r, id: r.id || null })) }));
  });
  const up = (i: number, patch: Partial<Addon>) => setRows((rs) => rs.map((x, k) => (k === i ? { ...x, ...patch } : x)));
  const tr = (i: number, l: L, patch: Partial<{ name: string; description: string | null }>) => {
    const cur = rows[i].translations[l] ?? { name: "", description: null };
    up(i, { translations: { ...rows[i].translations, [l]: { ...cur, ...patch } } });
  };
  const blank: Addon = { id: 0, image_key: null, image_url: null, price_inr_minor: 0, price_usd_minor: 0, max_qty: 1, ships_home: false, active: true,
    translations: { en: { name: "", description: null } } };
  return (
    <Card title="Chadhava items (optional add-ons)">
      <p className="mb-3 text-small text-ink-600">Offerings devotees can add to their booking, e.g. a flower garland or a sari for the deity.</p>
      {view}
      {rows.map((a, i) => (
        <div key={a.id || `new-${i}`} className={cx("mb-4 rounded-btn border border-gold-line p-3", !a.active && "opacity-70")}>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">{a.translations.en?.name || "New item"}{!a.active && " (hidden)"}</p>
            <button type="button" className="pp-link text-sindoor-600" onClick={() => {
              if (!a.id) { setRows(rows.filter((_, k) => k !== i)); return; }
              if (!window.confirm(`Delete “${a.translations.en?.name || "this item"}”?`)) return;
              run(async () => { onSaved(await api<Puja>(`/admin/pujas/${puja.id}/addons/${a.id}`, { method: "DELETE" })); }, "Item deleted.");
            }}>Delete item</button>
          </div>
          <div className="grid gap-3 lg:grid-cols-[10rem_1fr]">
            <div>
              {a.image_key
                ? <img src={mediaSrc(a.image_key, a.image_url)} alt="" className="mb-2 aspect-square w-full rounded-btn border border-marble-200 bg-marble-100 object-cover" />
                : <div className="mb-2 flex aspect-square w-full items-center justify-center rounded-btn border border-dashed border-marble-400 text-small text-ink-600">No image</div>}
              <label className={cx("pp-btn pp-btn-secondary min-h-10 w-full cursor-pointer text-small", uploading !== null && "pointer-events-none opacity-60")}>
                {uploading === i ? "Uploading…" : a.image_key ? "Replace image" : "Upload image"}
                <input type="file" accept="image/*" className="sr-only" disabled={uploading !== null} onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (!f) return;
                  const alt = Object.fromEntries(LOCALES.map((l) => [l, a.translations[l]?.name ?? ""]).filter(([, v]) => v));
                  if (!Object.keys(alt).length) { window.alert("Enter the item's name first (it is used as the image description)."); return; }
                  setUploading(i);
                  run(async () => {
                    const r = await resumableUpload(f, { purpose: "image", temple_id: puja.temple_id, alt });
                    up(i, { image_key: String(r.key), image_url: r.url ? String(r.url) : null });
                  }, "Image uploaded. Click “Save” to keep it.").finally(() => setUploading(null));
                }} />
              </label>
              {a.image_key && <button type="button" className="pp-link mt-1 text-small text-sindoor-600" onClick={() => up(i, { image_key: null, image_url: null })}>Remove image</button>}
            </div>
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                {LOCALES.map((l) => (
                  <div key={l} lang={l} className="space-y-1">
                    <Field label={`Name (${LANG[l]})`}><input className="pp-input" value={a.translations[l]?.name ?? ""} onChange={(e) => tr(i, l, { name: e.target.value })} /></Field>
                    <textarea className="pp-input min-h-16 text-small" placeholder={`Description (${LANG[l]}, optional)`} aria-label={`Description (${LANG[l]})`}
                      value={a.translations[l]?.description ?? ""} onChange={(e) => tr(i, l, { description: e.target.value || null })} />
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 items-end gap-2 sm:grid-cols-4">
                <PricePair inr={a.price_inr_minor} usd={a.price_usd_minor} onChange={(inr, usd) => up(i, { price_inr_minor: inr, price_usd_minor: usd })} />
                <Field label="Max quantity"><input type="number" min={1} max={50} className="pp-input" value={a.max_qty} onChange={(e) => up(i, { max_qty: Number(e.target.value) })} /></Field>
                <div className="space-y-1 pb-2 text-small">
                  <label className="flex items-center gap-2"><input type="checkbox" checked={a.ships_home} onChange={(e) => up(i, { ships_home: e.target.checked })} /> Ships home</label>
                  <label className="flex items-center gap-2"><input type="checkbox" checked={a.active} onChange={(e) => up(i, { active: e.target.checked })} /> Shown on site</label>
                </div>
              </div>
            </div>
          </div>
        </div>
      ))}
      <button type="button" className="pp-btn pp-btn-secondary" onClick={() => setRows([...rows, blank])}>+ Add item</button>
      <p className="mt-2 text-small text-ink-600">Items that were ever ordered can only be hidden, not deleted.</p>
    </Card>
  );
}

// ------------------------------------------------------------------ 6. advanced (optional)
function AdvancedStep({ p, set, drafts, edit, locale, setLocale, onSave }: {
  p: Puja; set: (p: Partial<Puja>) => void; drafts: Record<L, Tr>; edit: (l: L, patch: Partial<Tr>) => void;
  locale: L; setLocale: (l: L) => void; onSave: Saver;
}) {
  useSaver("advanced", "all", onSave);
  const tr = drafts[locale];
  const prasad = p.prasad_box ?? [];
  const prasadOpts = [...PRASAD, ...prasad.filter((v) => !PRASAD.some(([k]) => k === v)).map((v): [string, string] => [v, v])];
  return (
    <>
      <p className="mb-4 rounded-card border border-gold-line bg-gold-100/40 p-3 text-small">
        Everything here is optional — sensible defaults are used if you leave it. Click <b>Skip</b> to go straight to publishing.
      </p>
      <Card title="Search engines (SEO)">
        <p className="mb-3 text-small text-ink-600">
          What Google and WhatsApp/Facebook link previews show — not what appears on the page itself. Leave blank to use the page title and
          subtitle. Fill in only if you want a different, search-friendly wording (e.g. “Pradosha Puja at Kashi Vishwanath — Book Online”).
        </p>
        <LocaleTabs p={p} locale={locale} setLocale={setLocale} />
        <div className="grid gap-4" lang={locale}>
          <Field label={`Search title (${(tr.meta_title ?? "").length}/60)`} hint="Best under 60 characters.">
            <input className="pp-input" placeholder={tr.title || "Uses the page title"} value={tr.meta_title ?? ""} onChange={(e) => edit(locale, { meta_title: e.target.value })} />
          </Field>
          <Field label={`Search description (${(tr.meta_description ?? "").length}/155)`} hint="Best under 155 characters.">
            <textarea className="pp-input" placeholder={tr.subtitle || "Uses the subtitle"} value={tr.meta_description ?? ""} onChange={(e) => edit(locale, { meta_description: e.target.value })} />
          </Field>
        </div>
      </Card>
      <Card title="Page address & search tags">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Web address" hint={`pujapath…/pujas/${p.slug}-${p.id}. Made from the title if left as is.`}>
            <input className="pp-input" value={p.slug} onChange={(e) => set({ slug: e.target.value })} />
          </Field>
          <Field label="Deity tags" hint="Comma separated, e.g. shiva, parvati"><input className="pp-input" defaultValue={csv(p.deity_tags)} onBlur={(e) => set({ deity_tags: list(e.target.value) })} /></Field>
          <Field label="Dosha tags" hint="Comma separated, e.g. shani, rahu-ketu"><input className="pp-input" defaultValue={csv(p.dosha_tags)} onBlur={(e) => set({ dosha_tags: list(e.target.value) })} /></Field>
          <Field label="Purpose tags" hint="Comma separated, e.g. health, career"><input className="pp-input" defaultValue={csv(p.benefit_tags)} onBlur={(e) => set({ benefit_tags: list(e.target.value) })} /></Field>
        </div>
      </Card>
      <Card title="Prasad & delivery">
        <fieldset>
          <legend className="mb-2 text-small font-semibold">Prasad box contents (shelf-stable only; none = no prasad box)</legend>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {prasadOpts.map(([v, label]) => (
              <label key={v} className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={prasad.includes(v)}
                onChange={(e) => { const n = toggle(prasad, v, e.target.checked); set({ prasad_box: n.length ? n : null }); }} /> {label}</label>
            ))}
          </div>
        </fieldset>
        <Field label="Video delivery time (hours)" hint="How soon after the puja the video is promised. Blank = site default.">
          <input type="number" min={1} className="pp-input max-w-48" value={p.video_sla_hours ?? ""}
            onChange={(e) => set({ video_sla_hours: e.target.value ? Number(e.target.value) : null })} />
        </Field>
      </Card>
    </>
  );
}

function DangerZone({ puja, onChanged }: { puja: Puja; onChanged: () => void }) {
  const router = useRouter();
  const { run, busy, view } = useAction();
  const live = LOCALES.filter((l) => puja.translations[l]?.published);
  const title = puja.translations.en?.title || puja.slug;
  return (
    <Card title="Remove" className="border border-sindoor-600/50">
      {view}
      <div className="flex flex-wrap gap-3">
        <button type="button" className="pp-btn pp-btn-secondary" disabled={busy || !live.length} onClick={() => {
          if (!window.confirm(`Hide “${title}” from the site in all languages? Existing bookings are not affected.`)) return;
          run(async () => { await api(`/admin/pujas/${puja.id}/unpublish`, { method: "POST", json: { locales: live } }); onChanged(); }, "Unpublished: hidden from the site.");
        }}>Unpublish everywhere</button>
        <button type="button" className="pp-btn border border-sindoor-600 text-sindoor-600" disabled={busy} onClick={() => {
          if (window.prompt(`This permanently deletes “${title}” with its dates, packages, items and copy.\nType DELETE to confirm.`) !== "DELETE") return;
          run(async () => { await api(`/admin/pujas/${puja.id}`, { method: "DELETE" }); router.push("/admin/catalog"); }, "Puja deleted.");
        }}>Delete puja</button>
      </div>
      <p className="mt-2 text-small text-ink-600">Pujas that were ever booked can&apos;t be deleted; unpublish them instead.</p>
    </Card>
  );
}

// ------------------------------------------------------------------ 7. review & publish
const FIELD_LABEL: Record<string, string> = {
  tradition: "Tradition", sankalp_language: "Sankalp language", duration_minutes: "Duration", priests_count: "Number of priests",
  deliverables: "What the devotee receives", images: "Photos", packages: "Packages", seva_plan: "Seva plan",
  "temple.venue_type": "Temple venue type", "temple.name": "Temple name in this language", translation: "Page content",
  title: "Title", subtitle: "Subtitle", occasion_chip: "Occasion tag", about_md: "About this puja", benefits: "Why devotees offer it",
  rituals: "Ritual steps", meta_title: "Search title", meta_description: "Search description",
};
const FIELD_STEP: [RegExp, Step | "temple"][] = [
  [/^(tradition|sankalp_language|duration_minutes|priests_count|deliverables)$/, "basics"],
  [/^images/, "photos"], [/^(packages|seva_plan)/, "pricing"], [/^meta_/, "advanced"], [/^temple\./, "temple"], [/.*/, "content"],
];

function describe(e: Err) {
  const base = e.field.split(/[.[]/)[0];
  const label = FIELD_LABEL[e.field] ?? FIELD_LABEL[base] ?? e.field;
  const m = /\[(\d+)\]/.exec(e.field);
  const where = m ? ` #${Number(m[1]) + 1}` : "";
  const what = e.code === "required" ? (e.field.endsWith(".alt") ? "needs a description" : e.field.endsWith(".price") ? "needs a price" : "is missing")
    : e.code === "missing" ? "not written yet"
    : e.code === "placeholder" ? "still has placeholder text (TODO, [ ], {{ }})"
    : e.code === "more_than_one_main" ? "has more than one main ritual"
    : e.code === "template_variable_empty" ? "is missing (add it on the Temples page)"
    : e.code.startsWith("banned_phrase:") ? `uses a forbidden claim: “${e.code.slice(14)}”` : e.code;
  return `${label}${where} ${what}`;
}

function NoDatesWarning() {
  return (
    <p role="alert" className="mb-3 rounded-card border border-sindoor-600 p-3 text-sindoor-600">
      No dates are open for booking. Until you add one, this puja can&apos;t be booked and won&apos;t appear in listings.
    </p>
  );
}

function PublishStep({ p, errors, busy, unsaved, openDates, onCheck, goTo, onChanged }: {
  p: Puja; errors: Err[] | null; busy: boolean; unsaved: boolean; openDates: number | null; onCheck: () => void; goTo: (s: Step) => void; onChanged: () => void;
}) {
  const { run, busy: publishing, view } = useAction();
  const saved = LOCALES.filter((l) => p.translations[l]);
  const blocked = (l: L) => (errors ?? []).some((e) => e.locale === null || e.locale === l);
  const publish = (locales: L[], on = true) => run(async () => {
    await api(`/admin/pujas/${p.id}/${on ? "publish" : "unpublish"}`, { method: "POST", json: { locales } });
    onChanged();
  }, on ? `Published ${locales.map((l) => LANG[l]).join(", ")}. Live pages updated.` : "Hidden from the site.");
  return (
    <>
      {unsaved && (
        <p role="alert" className="mb-4 rounded-card border border-sindoor-600 p-3 text-sindoor-600">
          You have unsaved page text. <button type="button" className="pp-link" onClick={() => goTo("content")}>Go back and save it</button> before publishing.
        </p>
      )}
      <Card title="Checklist" actions={<button type="button" className="pp-btn pp-btn-secondary min-h-10" disabled={busy} onClick={onCheck}>Check again</button>}>
        {errors === null ? <p className="text-ink-600">Checking…</p> : errors.length === 0 ? (
          <p className="text-tulsi-600">✓ Everything required is filled in. Ready to publish.</p>
        ) : (
          <ul className="space-y-2">
            {errors.map((e, i) => {
              const target = FIELD_STEP.find(([re]) => re.test(e.field))![1];
              return (
                <li key={i} className="flex flex-wrap items-center justify-between gap-2 rounded-btn border border-sindoor-600/40 p-2">
                  <span><span className="text-small font-semibold text-ink-600">{e.locale ? LANG[e.locale as L] ?? e.locale : "All languages"}</span> · {describe(e)}</span>
                  {target === "temple"
                    ? <Link href="/admin/temples" className="pp-link">Open Temples</Link>
                    : <button type="button" className="pp-link" onClick={() => goTo(target)}>Fix in {STEPS.find((s) => s.id === target)!.label}</button>}
                </li>
              );
            })}
          </ul>
        )}
        {openDates === 0 && (
          <div role="alert" className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-btn border border-sindoor-600 bg-sindoor-600/5 p-2">
            <span><span className="text-small font-semibold text-sindoor-600">Warning</span> · No dates open for booking — devotees can&apos;t book
              and it won&apos;t appear in listings. You can still publish.</span>
            <button type="button" className="pp-link" onClick={() => goTo("dates")}>Add dates</button>
          </div>
        )}
      </Card>
      <Card title="Publish">
        {view}
        {!saved.length ? <p className="text-ink-600">Write and save the page content first.</p> : (
          <div className="grid gap-2">
            {saved.map((l) => {
              const live = !!p.translations[l]?.published;
              return (
                <div key={l} className="flex flex-wrap items-center gap-3 rounded-btn border border-marble-200 p-2">
                  <span className="min-w-24 font-semibold">{LANG[l]}</span>
                  <Badge tone={live ? "green" : "grey"}>{live ? "live" : "draft"}</Badge>
                  <a href={`/${l}/preview/${p.id}`} target="_blank" rel="noreferrer" className="pp-link text-small">Preview</a>
                  <span className="flex-1" />
                  {live && <button type="button" className="pp-btn pp-btn-secondary min-h-10" disabled={publishing} onClick={() => publish([l], false)}>Unpublish</button>}
                  <button type="button" className="pp-btn pp-btn-primary min-h-10" disabled={publishing || errors === null || blocked(l)}
                    onClick={() => publish([l])}>{live ? "Publish changes" : "Publish"}</button>
                </div>
              );
            })}
            <button type="button" className="pp-btn pp-btn-primary mt-2 sm:w-fit" disabled={publishing || errors === null || saved.some(blocked)}
              onClick={() => publish(saved)}>Publish all languages</button>
          </div>
        )}
      </Card>
    </>
  );
}
