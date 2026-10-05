import { getRequestConfig } from "next-intl/server";

import { DEFAULT_LOCALE, isLocale, type Locale } from "./config";

const loaders: Record<Locale, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("@pujapath/locales/en.json"),
  hi: () => import("@pujapath/locales/hi.json"),
  ta: () => import("@pujapath/locales/ta.json"),
  te: () => import("@pujapath/locales/te.json"),
};

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = isLocale(requested) ? requested : DEFAULT_LOCALE;
  return { locale, messages: (await loaders[locale]()).default, timeZone: "Asia/Kolkata" };
});
