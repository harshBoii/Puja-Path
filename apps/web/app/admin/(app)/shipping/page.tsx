"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Badge, PageTitle, Table, statusTone, useApi } from "@/components/admin/ui";

type S = { id: string; booking_id: string; code: string; event_id: number; status: string; awb: string | null; courier: string | null;
  tracking_url: string | null; label_url: string | null; address: Record<string, string> };

export default function ShippingPage() {
  return <Suspense><Shipping /></Suspense>;
}

/** Shipments by event; bulk-create with the courier from the event screen; labels and tracking here. */
function Shipping() {
  const sp = useSearchParams();
  const ev = sp.get("event_id");
  const { data } = useApi<S[]>(`/admin/shipping${ev ? `?event_id=${ev}` : ""}`);
  return (
    <>
      <PageTitle>Shipping {ev && <span className="text-h3 text-ink-600">· event {ev}</span>}</PageTitle>
      <Table head={["Booking", "Event", "Status", "Courier / AWB", "Address", "Label"]} rows={(data ?? []).map((s) => [
        <Link key="b" href={`/admin/bookings/${s.booking_id}`} className="pp-link">{s.code}</Link>,
        <Link key="e" href={`/admin/events/${s.event_id}`} className="pp-link">{s.event_id}</Link>,
        <Badge key="s" tone={statusTone(s.status)}>{s.status}</Badge>,
        s.tracking_url ? <a key="t" href={s.tracking_url} target="_blank" rel="noreferrer" className="pp-link">{s.courier} {s.awb}</a> : "—",
        [s.address.city, s.address.pincode].filter(Boolean).join(" "),
        s.label_url ? <a key="l" href={s.label_url} target="_blank" rel="noreferrer" className="pp-link">Print</a> : "—"])} empty="No shipments." />
    </>
  );
}
