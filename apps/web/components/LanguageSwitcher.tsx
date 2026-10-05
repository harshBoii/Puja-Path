"use client";
import { IconGlobe } from "@pujapath/ui";
import { usePathname } from "next/navigation";
import { useId } from "react";

import { LOCALE_COOKIE, LOCALES, NATIVE_NAMES, type Locale } from "@/i18n/config";

/** Keeps you on the same page if it exists in the target language (read from the page's hreflang
 *  alternates); otherwise goes to that language's listing. */
export function switchLocale(target: Locale, pathname: string) {
  document.cookie = `${LOCALE_COOKIE}=${target}; path=/; max-age=31536000; samesite=lax`;
  const links = Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="alternate"][hreflang]'));
  const declared = links.filter((l) => l.hreflang !== "x-default");
  const match = declared.find((l) => l.hreflang === target);
  let dest: string;
  if (match) dest = new URL(match.href).pathname;
  else if (declared.length) dest = `/${target}/pujas`;
  else dest = pathname.replace(/^\/[a-z]{2}(?=\/|$)/, `/${target}`);
  window.location.assign(dest + window.location.search);
}

export default function LanguageSwitcher({ current, label }: { current: Locale; label: string }) {
  const pathname = usePathname();
  const id = useId();
  return (
    <div className="relative flex items-center">
      <label htmlFor={id} className="sr-only">{label}</label>
      <IconGlobe size={20} className="pointer-events-none absolute left-3 text-gold-700" />
      <select id={id} value={current} onChange={(e) => switchLocale(e.target.value as Locale, pathname)}
        className="min-h-12 appearance-none rounded-btn border border-marble-200 bg-surface py-2 pl-9 pr-3 text-small font-medium text-ink-900">
        {LOCALES.map((l) => <option key={l} value={l} lang={l}>{NATIVE_NAMES[l]}</option>)}
      </select>
    </div>
  );
}
