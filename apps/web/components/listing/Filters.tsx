"use client";
import { BottomSheet, IconFilter, IconSearch } from "@pujapath/ui";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

type Opt = { value: string; label: string };
export type FilterGroups = { key: string; label: string; options: Opt[] }[];

/** Filter chips synced to the URL. Mobile: bottom sheet with Apply/Clear. Desktop: inline chips. */
export default function Filters({ groups, sortOptions, labels }: {
  groups: FilterGroups; sortOptions: Opt[];
  labels: { filters: string; apply: string; clear: string; close: string; sort: string; search: string; placeholder: string };
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(groups.map((g) => [g.key, params.get(g.key) ?? ""])));

  const push = (next: Record<string, string>) => {
    const qs = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) { if (v) qs.set(k, v); else qs.delete(k); }
    qs.delete("offset");
    router.push(`${pathname}${qs.toString() ? `?${qs}` : ""}`, { scroll: false });
  };
  const active = groups.filter((g) => params.get(g.key)).length;

  const chips = (g: FilterGroups[number], value: string, onPick: (v: string) => void) => (
    <div key={g.key} className="mb-4">
      <p className="mb-2 font-semibold">{g.label}</p>
      <div className="flex flex-wrap gap-2">
        {g.options.map((o) => (
          <button key={o.value} type="button" className="pp-chip" aria-pressed={value === o.value}
            onClick={() => onPick(value === o.value ? "" : o.value)}>{o.label}</button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      <form role="search" className="relative" onSubmit={(e) => {
        e.preventDefault();
        push({ q: String(new FormData(e.currentTarget).get("q") ?? "").trim() });
      }}>
        <label htmlFor="pp-q" className="sr-only">{labels.search}</label>
        <IconSearch className="pointer-events-none absolute left-3 top-3 text-gold-700" />
        <input id="pp-q" name="q" type="search" defaultValue={params.get("q") ?? ""} placeholder={labels.placeholder}
          className="pp-input pl-10" />
      </form>
      <div className="flex items-center gap-2">
        <button type="button" className="pp-chip md:hidden" onClick={() => setOpen(true)} aria-haspopup="dialog">
          <IconFilter size={18} className="mr-1" />{labels.filters}{active ? ` (${active})` : ""}
        </button>
        <label className="ml-auto flex items-center gap-2 text-small">
          <span>{labels.sort}</span>
          <select className="pp-input min-h-12 w-auto py-1" value={params.get("sort") ?? "soonest"}
            onChange={(e) => push({ sort: e.target.value === "soonest" ? "" : e.target.value })}>
            {sortOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      </div>
      <div className="hidden md:block">
        {groups.map((g) => chips(g, params.get(g.key) ?? "", (v) => push({ [g.key]: v })))}
      </div>
      <BottomSheet open={open} onClose={() => setOpen(false)} title={labels.filters} closeLabel={labels.close}
        footer={<>
          <button type="button" className="pp-btn pp-btn-secondary flex-1" onClick={() => {
            const cleared = Object.fromEntries(groups.map((g) => [g.key, ""]));
            setDraft(cleared); push(cleared); setOpen(false);
          }}>{labels.clear}</button>
          <button type="button" className="pp-btn pp-btn-primary flex-1" onClick={() => { push(draft); setOpen(false); }}>
            {labels.apply}
          </button>
        </>}>
        {groups.map((g) => chips(g, draft[g.key] ?? "", (v) => setDraft((d) => ({ ...d, [g.key]: v }))))}
      </BottomSheet>
    </div>
  );
}
