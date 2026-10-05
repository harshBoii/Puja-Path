"use client";
import { DiyaLoader } from "@pujapath/ui";
import Link from "next/link";
import { useState } from "react";

import { Badge, PageTitle, Table, fmtDate, inr, statusTone, useApi } from "@/components/admin/ui";

type Row = { id: string; code: string; status: string; phone: string; name: string | null; title: string; starts_at: string;
  total_minor: number; currency: string; needs_call_reason: string | null };

export default function Bookings() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { data } = useApi<Row[]>(`/admin/bookings?q=${encodeURIComponent(query)}`);
  return (
    <>
      <PageTitle>Bookings</PageTitle>
      <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); setQuery(q); }}>
        <input className="pp-input" placeholder="Booking code, phone or name" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
        <button className="pp-btn pp-btn-primary">Search</button>
      </form>
      {!data ? <DiyaLoader label="Loading…" /> : (
        <Table head={["Code", "Status", "Name", "Phone", "Puja", "Date", "Total"]} rows={data.map((b) => [
          <Link key="c" href={`/admin/bookings/${b.id}`} className="pp-link font-semibold">{b.code}</Link>,
          <Badge key="s" tone={statusTone(b.status)}>{b.status}</Badge>, b.name, b.phone, b.title, fmtDate(b.starts_at), inr(b.total_minor, b.currency)])} />
      )}
    </>
  );
}
