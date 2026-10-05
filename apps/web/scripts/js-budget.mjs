// PRD §12: JavaScript under 200 KB gzipped on listing and detail pages. Run against a production build.
// Usage: node scripts/js-budget.mjs [baseUrl]
import zlib from "node:zlib";

const BASE = (process.argv[2] ?? "http://localhost:3000").replace(/\/$/, "");
const BUDGET_KB = 200;
const sitemap = await (await fetch(`${BASE}/api/v1/sitemap`)).json();
const puja = sitemap.pujas.find((p) => p.kind !== "seva" && p.locales.includes("en"));
const seva = sitemap.pujas.find((p) => p.kind === "seva" && p.locales.includes("en"));
const pages = ["/en", "/en/pujas", "/en/sevas", `/en/pujas/${puja.id}-${puja.slug}`, ...(seva ? [`/en/sevas/${seva.id}-${seva.slug}`] : [])];

let failed = false;
for (const path of pages) {
  const html = await (await fetch(BASE + path)).text();
  const srcs = [...new Set([...html.matchAll(/<script[^>]+src="([^"]+\.js[^"]*)"/g)].map((m) => m[1]))];
  let bytes = 0;
  for (const s of srcs) bytes += zlib.gzipSync(Buffer.from(await (await fetch(BASE + s)).arrayBuffer())).length;
  const kb = bytes / 1024;
  const ok = kb <= BUDGET_KB;
  failed ||= !ok;
  console.log(`${ok ? "ok  " : "FAIL"} ${path}: ${kb.toFixed(1)} KB gz JS (${srcs.length} files)`);
}
if (failed) { console.error(`\nOver the ${BUDGET_KB} KB budget.`); process.exit(1); }
