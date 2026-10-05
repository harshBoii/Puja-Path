import { BCP47, type Locale } from "@/i18n/config";

export function money(minor: number | null | undefined, currency: string, locale: string): string {
  if (minor === null || minor === undefined) return "";
  return new Intl.NumberFormat(BCP47[locale as Locale] ?? "en-IN", {
    style: "currency", currency, maximumFractionDigits: minor % 100 === 0 ? 0 : 2,
  }).format(minor / 100);
}

export function dateIST(iso: string, locale: string, opts: Intl.DateTimeFormatOptions = {}): string {
  return new Intl.DateTimeFormat(BCP47[locale as Locale] ?? "en-IN", {
    timeZone: "Asia/Kolkata", weekday: "short", day: "numeric", month: "short", ...opts,
  }).format(new Date(iso));
}

export function timeIST(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(BCP47[locale as Locale] ?? "en-IN", {
    timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit",
  }).format(new Date(iso));
}

/** "{id}-{slug}" -> id */
export function idFromSlug(param: string): number | null {
  const id = Number.parseInt(param.split("-")[0], 10);
  return Number.isFinite(id) ? id : null;
}

export function pujaPath(p: { id: number; slug: string; kind: string }): string {
  return `/${p.kind === "seva" ? "sevas" : "pujas"}/${p.id}-${p.slug}`;
}

export function whatsappUrl(e164: string, text: string): string {
  return `https://wa.me/${e164.replace(/\D/g, "")}?text=${encodeURIComponent(text)}`;
}

/** Renders {tokens} in CMS text (FAQ answers) from site_config so a promise is never typed twice. */
export function renderTokens(text: string, tokens: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (m, k) => (k in tokens ? String(tokens[k]) : m));
}

export function supportDays(days: number[], locale: string): string {
  const fmt = new Intl.DateTimeFormat(BCP47[locale as Locale] ?? "en-IN", { weekday: "short", timeZone: "UTC" });
  // 2024-01-01 was a Monday (Python weekday 0)
  const name = (d: number) => fmt.format(new Date(Date.UTC(2024, 0, 1 + d)));
  if (days.length === 7) return `${name(0)}–${name(6)}`;
  return days.map(name).join(", ");
}
