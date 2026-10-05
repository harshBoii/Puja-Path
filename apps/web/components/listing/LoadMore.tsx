"use client";
import { useState } from "react";

import PujaCardItem from "@/components/PujaCardItem";
import type { Listing, PujaCardData } from "@/lib/types";

/** "Load more" (12 per page); end state reads "You've seen all N pujas". */
export default function LoadMore({ endpoint, query, initial, labels }: {
  endpoint: string; query: string; initial: Listing; labels: { more: string; done: string; error: string };
}) {
  const [items, setItems] = useState<PujaCardData[]>(initial.items);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const done = items.length >= initial.total;
  const more = async () => {
    setLoading(true);
    setError(false);
    try {
      const qs = new URLSearchParams(query);
      qs.set("offset", String(items.length));
      const res = await fetch(`/api/v1${endpoint}?${qs}`);
      const data: Listing = await res.json();
      setItems((x) => [...x, ...data.items.filter((p) => !x.some((y) => y.id === p.id))]);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };
  return (
    <>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((p) => <li key={p.id}><PujaCardItem p={p} /></li>)}
      </ul>
      <div className="mt-8 text-center" aria-live="polite">
        {done ? <p className="text-ink-600">{labels.done}</p> : (
          <button type="button" className="pp-btn pp-btn-secondary" onClick={more} disabled={loading}>{labels.more}</button>
        )}
        {error && <p role="alert" className="mt-2 text-sindoor-600">{labels.error}</p>}
      </div>
    </>
  );
}
