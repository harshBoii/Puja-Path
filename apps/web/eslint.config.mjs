import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const noRawInternalLink = require("./eslint-rules/no-raw-internal-link.js");

const config = [
  ...nextVitals,
  ...nextTs,
  {
    plugins: { pujapath: { rules: { "no-raw-internal-link": noRawInternalLink } } },
    rules: {
      "pujapath/no-raw-internal-link": "error",
      "@next/next/no-img-element": "off", // images come pre-sized from R2/CDN (PRD §3)
      "@next/next/no-html-link-for-pages": "off", // replaced by pujapath/no-raw-internal-link
    },
  },
  { ignores: [".next/**", "next-env.d.ts", "lib/api-types.ts", "eslint-rules/**"] },
];

export default config;
