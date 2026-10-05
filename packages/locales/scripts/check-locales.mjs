// CI guard for locale files (PRD §12):
//  1. every locale has exactly the same keys as en.json
//  2. every string keeps the same {placeholders} as English
//  3. no literal hour count anywhere (SLA, cutoff and support hours must come from site_config tokens)
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..");
const LOCALES = ["en", "hi", "ta", "te"];
const HOUR_LITERAL = /\d+\s*(?:-|–)?\s*(?:hours?|hrs?|h\b|घंटे|घंटा|గంటల|గంట|மணி)/iu;

function flatten(obj, prefix = "", out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object") flatten(v, key, out);
    else out[key] = String(v);
  }
  return out;
}

function placeholders(s) {
  // top-level ICU arguments only: {name} or {count, plural, ...}
  const names = new Set();
  let depth = 0;
  for (let i = 0; i < s.length; i++) {
    if (s[i] === "{") {
      if (depth === 0) {
        const m = /^\{\s*([a-zA-Z_][\w]*)/.exec(s.slice(i));
        if (m) names.add(m[1]);
      }
      depth++;
    } else if (s[i] === "}") depth--;
  }
  return [...names].sort().join(",");
}

const files = Object.fromEntries(
  LOCALES.map((l) => [l, flatten(JSON.parse(readFileSync(join(dir, `${l}.json`), "utf8")))]),
);
const errors = [];
const enKeys = Object.keys(files.en);
for (const l of LOCALES) {
  const keys = new Set(Object.keys(files[l]));
  for (const k of enKeys) if (!keys.has(k)) errors.push(`${l}: missing key ${k}`);
  for (const k of keys) if (!(k in files.en)) errors.push(`${l}: extra key ${k}`);
  for (const [k, v] of Object.entries(files[l])) {
    if (k in files.en && placeholders(v) !== placeholders(files.en[k]))
      errors.push(`${l}: ${k} placeholders {${placeholders(v)}} != en {${placeholders(files.en[k])}}`);
    if (HOUR_LITERAL.test(v)) errors.push(`${l}: ${k} contains a literal hour count: "${v}"`);
    if (!v.trim()) errors.push(`${l}: ${k} is empty`);
  }
}
if (errors.length) {
  console.error(errors.join("\n"));
  console.error(`\n${errors.length} locale problem(s).`);
  process.exit(1);
}
console.log(`locales ok: ${LOCALES.join(", ")} — ${enKeys.length} keys each, no literal hour counts`);
