// Takes only an event ID (PRD §12): the deadline always comes from the real booking_cutoff_at.
import { getTranslations } from "next-intl/server";

import { getCountdown } from "@/lib/api";
import CountdownText from "./CountdownText";

export default async function BookingCountdown({ eventId }: { eventId: number }) {
  const data = await getCountdown(eventId);
  if (!data) return null;
  if (!data.show) return null; // the API decides: real cutoff, under 72 hours
  const remainingMs = data.remaining_seconds * 1000;
  const t = await getTranslations();
  return (
    <p className="inline-flex items-center gap-2 rounded-btn border border-gold-600 bg-gold-100 px-3 py-2 font-medium">
      <CountdownText deadlineIso={data.booking_cutoff_at} initialRemainingMs={remainingMs} template={t("puja.closesIn", { time: "{time}" })} />
    </p>
  );
}
