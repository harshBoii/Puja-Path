import { GlyphLotus } from "@pujapath/ui";
import { headers } from "next/headers";

import { LOCALES, NATIVE_NAMES, isLocale } from "@/i18n/config";
import { getConfig } from "@/lib/api";
import en from "@pujapath/locales/en.json";
import hi from "@pujapath/locales/hi.json";
import ta from "@pujapath/locales/ta.json";
import te from "@pujapath/locales/te.json";

const MESSAGES = { en, hi, ta, te };

/** First visit with no language cookie: full-screen picker, four large buttons, each in its own script.
 *  The browser's preferred language is listed first. */
export default async function LanguagePicker() {
  const config = await getConfig();
  const accept = (await headers()).get("accept-language") ?? "";
  const preferred = accept.split(",").map((p) => p.split(";")[0].trim().slice(0, 2)).find(isLocale);
  const order = preferred ? [preferred, ...LOCALES.filter((l) => l !== preferred)] : [...LOCALES];
  return (
    <main className="pp-marble flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <GlyphLotus size={56} className="text-gold-600" />
      <p className="pp-foil-text mt-3 font-display text-display">{config.brand}</p>
      <div className="mt-6 space-y-1 text-center">
        {order.map((l) => (
          <h1 key={l} lang={l} className={l === order[0] ? "text-h2" : "text-small text-ink-600"}>{MESSAGES[l].language.pickTitle}</h1>
        ))}
      </div>
      <ul className="mt-8 grid w-full max-w-md gap-3">
        {order.map((l) => (
          <li key={l}>
            {/* eslint-disable-next-line pujapath/no-raw-internal-link -- the picker is where the locale is chosen */}
            <a href={`/${l}`} lang={l} hrefLang={l}
              className="pp-card pp-foil-border flex min-h-16 items-center justify-center text-h2 font-semibold text-ink-900 no-underline">
              {NATIVE_NAMES[l]}
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-6 max-w-md text-center text-small text-ink-600">{MESSAGES[order[0]].language.pickSubtitle}</p>
    </main>
  );
}
