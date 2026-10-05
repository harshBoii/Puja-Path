import {
  Cormorant_Garamond,
  DM_Sans,
  Noto_Sans_Devanagari,
  Noto_Sans_Tamil,
  Noto_Sans_Telugu,
  Noto_Serif_Devanagari,
  Noto_Serif_Tamil,
  Noto_Serif_Telugu,
} from "next/font/google";

import type { Locale } from "@/i18n/config";

// Fonts are only downloaded when the active locale's CSS uses them. Nothing is preloaded: on Indic pages a Latin
// preload would compete with the script font on slow 4G, and `display: swap` shows fallback text immediately.
const cormorant = Cormorant_Garamond({ subsets: ["latin"], weight: ["600"], variable: "--f-cormorant", display: "swap", preload: false });
const dmSans = DM_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--f-dmsans", display: "swap", preload: false });
const serifTe = Noto_Serif_Telugu({ subsets: ["telugu"], weight: ["600"], variable: "--f-serif-te", display: "swap", preload: false });
const sansTe = Noto_Sans_Telugu({ subsets: ["telugu"], weight: ["400", "600"], variable: "--f-sans-te", display: "swap", preload: false });
const serifHi = Noto_Serif_Devanagari({ subsets: ["devanagari"], weight: ["600"], variable: "--f-serif-hi", display: "swap", preload: false });
const sansHi = Noto_Sans_Devanagari({ subsets: ["devanagari"], weight: ["400", "600"], variable: "--f-sans-hi", display: "swap", preload: false });
const serifTa = Noto_Serif_Tamil({ subsets: ["tamil"], weight: ["600"], variable: "--f-serif-ta", display: "swap", preload: false });
const sansTa = Noto_Sans_Tamil({ subsets: ["tamil"], weight: ["400", "600"], variable: "--f-sans-ta", display: "swap", preload: false });

const BY_LOCALE: Record<Locale, { classes: string[]; display: string; body: string }> = {
  en: { classes: [cormorant.variable, dmSans.variable], display: "var(--f-cormorant)", body: "var(--f-dmsans)" },
  te: { classes: [serifTe.variable, sansTe.variable, dmSans.variable], display: "var(--f-serif-te)", body: "var(--f-sans-te), var(--f-dmsans)" },
  hi: { classes: [serifHi.variable, sansHi.variable, dmSans.variable], display: "var(--f-serif-hi)", body: "var(--f-sans-hi), var(--f-dmsans)" },
  ta: { classes: [serifTa.variable, sansTa.variable, dmSans.variable], display: "var(--f-serif-ta)", body: "var(--f-sans-ta), var(--f-dmsans)" },
};

export function fontsFor(locale: Locale) {
  const f = BY_LOCALE[locale];
  return {
    className: f.classes.join(" "),
    style: { "--font-display": `${f.display}, Georgia, serif`, "--font-body": `${f.body}, system-ui, sans-serif` } as React.CSSProperties,
  };
}

export const adminFonts = { className: `${cormorant.variable} ${dmSans.variable}`,
  style: { "--font-display": "var(--f-cormorant), Georgia, serif", "--font-body": "var(--f-dmsans), system-ui, sans-serif" } as React.CSSProperties };
