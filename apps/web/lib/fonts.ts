import {
  Hind,
  Hind_Guntur,
  Hind_Madurai,
  Martel,
  Noto_Serif_Tamil,
  Noto_Serif_Telugu,
  Playfair_Display,
} from "next/font/google";

import type { Locale } from "@/i18n/config";

// Editorial headings + highly familiar Indian body text, set bold for older readers:
// - headings: Playfair Display (Latin), Martel (Hindi: Indian newspaper serif), Noto Serif Telugu / Tamil
// - body: the Hind family by Indian Type Foundry (Hind, Hind Guntur for Telugu, Hind Madurai for Tamil) —
//   open, clear letterforms widely used in Indian apps and news, one consistent family across all four scripts.
// Fonts download only when the active locale's CSS uses them. Nothing is preloaded: on Indic pages a Latin
// preload would compete with the script font on slow 4G, and `display: swap` shows fallback text immediately.
const playfair = Playfair_Display({ subsets: ["latin"], weight: ["700", "800"], variable: "--f-playfair", display: "swap", preload: false });
const hind = Hind({ subsets: ["latin", "devanagari"], weight: ["400", "500", "600", "700"], variable: "--f-hind", display: "swap", preload: false });
const martel = Martel({ subsets: ["devanagari", "latin"], weight: ["700", "800"], variable: "--f-martel", display: "swap", preload: false });
const serifTe = Noto_Serif_Telugu({ subsets: ["telugu"], weight: ["700"], variable: "--f-serif-te", display: "swap", preload: false });
const hindTe = Hind_Guntur({ subsets: ["telugu", "latin"], weight: ["400", "500", "600", "700"], variable: "--f-hind-te", display: "swap", preload: false });
const serifTa = Noto_Serif_Tamil({ subsets: ["tamil"], weight: ["700"], variable: "--f-serif-ta", display: "swap", preload: false });
const hindTa = Hind_Madurai({ subsets: ["tamil", "latin"], weight: ["400", "500", "600", "700"], variable: "--f-hind-ta", display: "swap", preload: false });

const BY_LOCALE: Record<Locale, { classes: string[]; display: string; body: string }> = {
  en: { classes: [playfair.variable, hind.variable], display: "var(--f-playfair)", body: "var(--f-hind)" },
  hi: { classes: [martel.variable, hind.variable], display: "var(--f-martel)", body: "var(--f-hind)" },
  te: { classes: [serifTe.variable, hindTe.variable, playfair.variable], display: "var(--f-serif-te), var(--f-playfair)", body: "var(--f-hind-te)" },
  ta: { classes: [serifTa.variable, hindTa.variable, playfair.variable], display: "var(--f-serif-ta), var(--f-playfair)", body: "var(--f-hind-ta)" },
};

export function fontsFor(locale: Locale) {
  const f = BY_LOCALE[locale];
  return {
    className: f.classes.join(" "),
    style: { "--font-display": `${f.display}, Georgia, serif`, "--font-body": `${f.body}, system-ui, sans-serif` } as React.CSSProperties,
  };
}

export const adminFonts = { className: `${playfair.variable} ${hind.variable}`,
  style: { "--font-display": "var(--f-playfair), Georgia, serif", "--font-body": "var(--f-hind), system-ui, sans-serif" } as React.CSSProperties };
