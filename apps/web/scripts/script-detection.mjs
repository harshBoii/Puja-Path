// PRD §12 guard: render every public route in every locale and fail if more than 2% of the visible
// letters belong to another locale's script (proper nouns allowlisted). Also checks the viewport allows
// pinch-zoom and that no notranslate meta tag is present.
// Usage: node scripts/script-detection.mjs [baseUrl]   (default http://localhost:3000)

const BASE = (process.argv[2] ?? process.env.SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");
const LOCALES = ["en", "hi", "ta", "te"];
const THRESHOLD = 0.02;

const SCRIPTS = {
  latin: /\p{Script=Latin}/u,
  devanagari: /\p{Script=Devanagari}/u,
  tamil: /\p{Script=Tamil}/u,
  telugu: /\p{Script=Telugu}/u,
};
const OWN = { en: "latin", hi: "devanagari", ta: "tamil", te: "telugu" };

// Proper nouns and product terms that are correctly written in Latin on every locale.
const ALLOW = [
  "Puja Path", "WhatsApp", "UPI AutoPay", "UPI", "AutoPay", "IST", "INR", "USD", "OTP", "SMS", "PDF", "My Subscriptions",
  "Accept", "Refund", "English", "Vijayawada", "Kanchipuram", "Varanasi", "Hyderabad", "Andhra Pradesh", "Tamil Nadu",
  "Uttar Pradesh", "Telangana", "am", "pm", "AM", "PM",
];
// Each language's own name in its own script is expected in the language switcher on every page.
const NATIVE = ["తెలుగు", "हिन्दी", "தமிழ்", "English"];

function visibleText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<template[\s\S]*?<\/template>/gi, " ")
    .replace(/<option[\s\S]*?<\/option>/gi, " ") // the language switcher lists every language by design
    .replace(/<[^>]+>/g, " ")
    .replace(/&[a-z#0-9]+;/gi, " ");
}

function measure(text, locale) {
  let cleaned = text;
  for (const w of [...ALLOW, ...NATIVE].sort((a, b) => b.length - a.length)) cleaned = cleaned.split(w).join(" ");
  const counts = { latin: 0, devanagari: 0, tamil: 0, telugu: 0 };
  for (const ch of cleaned) for (const [name, re] of Object.entries(SCRIPTS)) if (re.test(ch)) { counts[name]++; break; }
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const foreign = total - counts[OWN[locale]];
  return { total, foreign, ratio: total ? foreign / total : 0, counts };
}

async function routes() {
  const res = await fetch(`${BASE}/api/v1/sitemap`);
  const data = await res.json();
  const out = Object.fromEntries(LOCALES.map((l) => [l, ["", "/pujas", "/sevas", "/temples", "/about", "/faq", "/contact",
    "/legal/terms", "/legal/privacy", "/legal/refunds", "/legal/shipping"]]));
  for (const p of data.pujas) for (const l of p.locales) out[l].push(`/${p.kind === "seva" ? "sevas" : "pujas"}/${p.id}-${p.slug}`);
  for (const t of data.temples) for (const l of t.locales) out[l].push(`/temples/${t.id}-${t.slug}`);
  return out;
}

const all = await routes();
const failures = [];
let checked = 0;
for (const locale of LOCALES) {
  for (const path of all[locale]) {
    const url = `${BASE}/${locale}${path}`;
    const res = await fetch(url, { headers: { cookie: `pp_locale=${locale}` } });
    if (!res.ok) { failures.push(`${url}: HTTP ${res.status}`); continue; }
    const html = await res.text();
    const viewport = /<meta[^>]+name="viewport"[^>]*content="([^"]*)"/i.exec(html)?.[1] ?? "";
    if (!viewport || /user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b/i.test(viewport))
      failures.push(`${url}: viewport blocks pinch-zoom ("${viewport}")`);
    if (/<meta[^>]+name="google"[^>]+notranslate/i.test(html)) failures.push(`${url}: has a notranslate meta tag`);
    const m = measure(visibleText(html), locale);
    checked++;
    if (m.ratio > THRESHOLD) failures.push(`${url}: ${(m.ratio * 100).toFixed(1)}% foreign script (${JSON.stringify(m.counts)})`);
  }
}
if (failures.length) {
  console.error(failures.join("\n"));
  console.error(`\n${failures.length} of ${checked} pages failed the script check.`);
  process.exit(1);
}
console.log(`script check ok: ${checked} pages, all under ${THRESHOLD * 100}% foreign script; zoom allowed everywhere`);
