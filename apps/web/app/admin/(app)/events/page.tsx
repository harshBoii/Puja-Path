"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { EventsManager } from "@/components/admin/EventsManager";
import { PageTitle } from "@/components/admin/ui";

export default function EventsPage() {
  return <Suspense><Events /></Suspense>;
}

/** Every puja date in one place: filter, add one or a repeating series, edit, delete. */
function Events() {
  const sp = useSearchParams();
  return (
    <>
      <PageTitle>Events</PageTitle>
      <EventsManager initialPujaId={sp.get("puja_id") ? Number(sp.get("puja_id")) : null} />
    </>
  );
}
