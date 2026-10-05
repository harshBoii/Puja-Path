"use client";
import { useState } from "react";

import PujaCardItem from "@/components/PujaCardItem";
import type { PujaCardData } from "@/lib/types";

type Tab = "all" | "deity" | "dosha" | "benefit";

/** Chip tabs All / Deity / Dosha / Purpose over the upcoming pujas; 6 cards shown. */
export default function UpcomingTabs({ items, tags, labels }: {
  items: PujaCardData[]; tags: { deity: string[]; dosha: string[]; benefit: string[] };
  labels: { all: string; deity: string; dosha: string; benefit: string; tag: Record<string, string> };
}) {
  const [tab, setTab] = useState<Tab>("all");
  const [value, setValue] = useState<string | null>(null);
  const field = (t: Tab): "deity_tags" | "dosha_tags" | "benefit_tags" =>
    t === "deity" ? "deity_tags" : t === "dosha" ? "dosha_tags" : "benefit_tags";
  const shown = (tab === "all" || !value ? items : items.filter((p) => p[field(tab)].includes(value))).slice(0, 6);
  return (
    <div>
      <div className="pp-scroll-x -mx-4 mb-3 flex gap-2 px-4" role="tablist">
        {(["all", "deity", "dosha", "benefit"] as Tab[]).filter((t) => t === "all" || tags[t].length).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className="pp-chip"
            data-selected={tab === t} onClick={() => { setTab(t); setValue(t === "all" ? null : tags[t][0]); }}>
            {labels[t]}
          </button>
        ))}
      </div>
      {tab !== "all" && (
        <div className="pp-scroll-x -mx-4 mb-4 flex gap-2 px-4">
          {tags[tab].map((v) => (
            <button key={v} type="button" className="pp-chip" aria-pressed={value === v} onClick={() => setValue(v)}>
              {labels.tag[v] ?? v}
            </button>
          ))}
        </div>
      )}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((p) => <li key={p.id}><PujaCardItem p={p} /></li>)}
      </ul>
    </div>
  );
}
