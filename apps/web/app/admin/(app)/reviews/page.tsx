"use client";
import { useState } from "react";

import { PageTitle, Table, fmtDate, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

type R = { id: string; rating: number; text: string | null; locale: string; status: string; code: string; title: string; at: string };

/** Nothing shows on the site before approval; only reviews from completed bookings exist. */
export default function Reviews() {
  const [status, setStatus] = useState("pending");
  const { data, reload } = useApi<R[]>(`/admin/reviews?status=${status}`);
  const { run, view } = useAction();
  const act = (id: string, s: "approved" | "rejected") => run(async () => { await api(`/admin/reviews/${id}`, { method: "POST", json: { status: s } }); reload(); }, `Review ${s}.`);
  return (
    <>
      <PageTitle>Reviews</PageTitle>
      <div className="mb-3 flex gap-2">{["pending", "approved", "rejected"].map((s) => <button key={s} className="pp-chip" data-selected={s === status} onClick={() => setStatus(s)}>{s}</button>)}</div>
      {view}
      <Table head={["When", "Booking", "Puja", "Rating", "Text", ""]} rows={(data ?? []).map((r) => [fmtDate(r.at), r.code, r.title, "★".repeat(r.rating),
        <span key="t" lang={r.locale}>{r.text}</span>,
        r.status === "pending" ? <span key="a" className="flex gap-3"><button className="pp-link" onClick={() => act(r.id, "approved")}>Approve</button>
          <button className="pp-link" onClick={() => act(r.id, "rejected")}>Reject</button></span> : r.status])} />
    </>
  );
}
