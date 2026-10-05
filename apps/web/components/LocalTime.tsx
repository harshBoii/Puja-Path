"use client";
import { BCP47, type Locale } from "@/i18n/config";
import { useBrowserValue } from "@/lib/hooks";

const browserTz = () => Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";

/** Shows the puja time in the visitor's own time zone when it differs from IST (NRI devotees). */
export default function LocalTime({ iso, locale, template }: { iso: string; locale: string; template: string }) {
  const tz = useBrowserValue(browserTz, "");
  if (!tz || tz === "Asia/Kolkata" || tz === "Asia/Calcutta") return null;
  const t = new Intl.DateTimeFormat(BCP47[locale as Locale] ?? "en-IN", {
    timeZone: tz, weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZoneName: "short",
  }).format(new Date(iso));
  return <span className="block text-small text-ink-600">{template.replace("{time}", t)}</span>;
}
