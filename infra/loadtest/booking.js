// k6 load test (M5). Run against STAGING with fake providers only:
//   k6 run -e BASE=https://staging.example -e AUTH=user:pass infra/loadtest/booking.js
// Scenarios: browsing (cached ISR pages + listing API) and the booking funnel up to a signed fake-gateway payment.
import http from "k6/http";
import encoding from "k6/encoding";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "http://localhost:3000";
const AUTH = __ENV.AUTH ? { Authorization: `Basic ${encoding.b64encode(__ENV.AUTH)}` } : {};
const LOCALES = ["te", "hi", "ta", "en"];

export const options = {
  scenarios: {
    browse: { executor: "ramping-vus", stages: [{ duration: "1m", target: 200 }, { duration: "3m", target: 200 }, { duration: "30s", target: 0 }], exec: "browse" },
    book: { executor: "constant-arrival-rate", rate: 5, timeUnit: "1s", duration: "4m", preAllocatedVUs: 40, exec: "book" },
  },
  thresholds: {
    "http_req_failed": ["rate<0.01"],
    "http_req_duration{scenario:browse}": ["p(95)<800"],
    "http_req_duration{scenario:book}": ["p(95)<1500"],
  },
};

const pick = (a) => a[Math.floor(Math.random() * a.length)];
const json = (body) => ({ headers: { ...AUTH, "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function setup() {
  const sm = http.get(`${BASE}/api/v1/sitemap`, { headers: AUTH }).json();
  return { pujas: sm.pujas.filter((p) => p.kind !== "seva" && p.locales.length) };
}

export function browse(data) {
  const l = pick(LOCALES);
  const p = pick(data.pujas.filter((x) => x.locales.includes(l)));
  check(http.get(`${BASE}/${l}`, { headers: AUTH }), { home: (r) => r.status === 200 });
  check(http.get(`${BASE}/${l}/pujas`, { headers: AUTH }), { listing: (r) => r.status === 200 });
  if (p) check(http.get(`${BASE}/${l}/pujas/${p.id}-${p.slug}`, { headers: AUTH }), { detail: (r) => r.status === 200 });
  sleep(1 + Math.random() * 2);
}

export function book(data) {
  const p = pick(data.pujas.filter((x) => x.locales.includes("en")));
  const detail = http.get(`${BASE}/api/v1/en/pujas/${p.id}`, { headers: AUTH }).json();
  if (!detail.event) return;
  const draft = http.post(`${BASE}/api/v1/drafts`, JSON.stringify({ puja_id: p.id, package_id: detail.packages[0].id, locale: "en" }),
    { headers: { ...AUTH, "Content-Type": "application/json" } });
  if (!check(draft, { draft: (r) => r.status === 201 })) return;
  const id = draft.json("id");
  const phone = `+9198${String(Math.floor(Math.random() * 1e8)).padStart(8, "0")}`;
  const nak = detail.requires_nakshatra ? "Rohini" : null;
  const body = json({ names: [{ name: "Load Test", gotra: "Kashyapa", nakshatra: nak }], whatsapp_e164: phone, consent_whatsapp: true });
  const view = http.put(`${BASE}/api/v1/drafts/${id}`, body.body, { headers: body.headers });
  if (!check(view, { names: (r) => r.status === 200 })) return;
  const otp = http.post(`${BASE}/api/v1/auth/otp/request`, JSON.stringify({ phone_e164: phone }), { headers: { ...AUTH, "Content-Type": "application/json" } });
  const verify = http.post(`${BASE}/api/v1/auth/otp/verify`, JSON.stringify({ phone_e164: phone, code: otp.json("dev_code") }),
    { headers: { ...AUTH, "Content-Type": "application/json" } });
  if (!check(verify, { login: (r) => r.status === 200 })) return;
  const pay = http.post(`${BASE}/api/v1/drafts/${id}/pay`, JSON.stringify({ consent_terms: true, expected_total_minor: view.json("pricing.total_minor") }),
    { headers: { ...AUTH, "Content-Type": "application/json" } });
  if (!check(pay, { pay: (r) => r.status === 200 })) return;
  const paid = http.post(`${BASE}/api/v1/dev/fake-gateway/${pay.json("checkout.order_id")}`, JSON.stringify({ outcome: "success" }),
    { headers: { ...AUTH, "Content-Type": "application/json" } });
  check(paid, { webhook: (r) => r.status === 200 });
  check(http.get(`${BASE}/api/v1/bookings/${id}/status`, { headers: AUTH }), { confirmed: (r) => r.json("status") === "confirmed" });
}
