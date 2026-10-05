import en from "@pujapath/locales/en.json";
import hi from "@pujapath/locales/hi.json";
import ta from "@pujapath/locales/ta.json";
import te from "@pujapath/locales/te.json";

export const MESSAGES = { en, hi, ta, te } as const;
export type Loc = keyof typeof MESSAGES;

/** Minimal message lookup for stories: "home.promiseVideo" + {hours: 48}. */
export function tr(locale: string, key: string, values: Record<string, string | number> = {}): string {
  const msg = key.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], MESSAGES[(locale as Loc) ?? "en"]);
  return String(msg ?? key).replace(/\{(\w+)\}/g, (m, k) => (k in values ? String(values[k]) : m));
}
