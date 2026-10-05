export const LOCALES = ["te", "hi", "ta", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "pp_locale";
export const CURRENCY_COOKIE = "pp_currency";

/** Each language written in its own script, for the picker and switcher. */
export const NATIVE_NAMES: Record<Locale, string> = { te: "తెలుగు", hi: "हिन्दी", ta: "தமிழ்", en: "English" };
export const BCP47: Record<Locale, string> = { te: "te-IN", hi: "hi-IN", ta: "ta-IN", en: "en-IN" };

export function isLocale(x: string | undefined | null): x is Locale {
  return !!x && (LOCALES as readonly string[]).includes(x);
}
