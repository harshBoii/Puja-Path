// M2 acceptance: a test-mode booking goes from the puja detail page to `confirmed`, in a real browser.
// Runs against fake providers (dev OTP code + fake gateway). Usage: node e2e/journey.mjs [baseUrl] [screenshot.png]
// Set CHROME_PATH to use an installed Chromium-based browser instead of Playwright's bundled one.
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://localhost:3000";
const out = process.argv[3];
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, headless: true });
const ctx = await browser.newContext({ viewport: { width: 412, height: 900 } });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(e.message));
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 200)); });
const t0 = Date.now();
await page.goto(`${base}/en/pujas/4-lakshmi-kubera-puja`, { waitUntil: "domcontentloaded" });
await page.getByRole("button", { name: "Book this puja" }).first().click();
await page.waitForURL(/\/en\/checkout\//, { timeout: 20000 });
await page.locator("#name-0").fill("Lakshmi Devi");
await page.locator("#gotra-0").fill("Bharadwaja");
await page.locator("#phone").fill("9876543210");
await page.getByRole("button", { name: "Continue" }).first().click();
await page.getByRole("heading", { name: "Offerings and prasad" }).waitFor();
await page.getByLabel("Send prasad to my home (India only)").check();
for (const [k, v] of [["name","Lakshmi"],["phone","9876543210"],["line1","12 Temple Street"],["city","Hyderabad"],["state","Telangana"],["pincode","500001"]])
  await page.locator(`#addr-${k}`).fill(v);
await page.locator("#addr-pincode").blur();
await page.getByRole("button", { name: "Continue" }).last().click();
await page.getByText("Send booking updates and my proof video on WhatsApp").click();
await page.getByText(/I agree to the/).click();
await page.getByRole("button", { name: "Send code" }).click();
const code = (await page.locator("text=Dev code:").locator("strong").textContent()).trim();
await page.getByLabel("6-digit code").fill(code);
await page.getByRole("button", { name: "Verify" }).click();
const payBtn = page.getByRole("button", { name: /^Pay / });
await payBtn.waitFor();
const payText = await payBtn.textContent();
await payBtn.click();
await page.getByRole("button", { name: "Simulate success" }).click();
await page.waitForURL(/success/, { timeout: 20000 });
await page.getByRole("heading", { name: "Your booking is confirmed" }).waitFor({ timeout: 20000 });
const bookingCode = await page.locator(".font-display.text-display").textContent();
console.log(JSON.stringify({ ok: true, pay: payText, code: bookingCode, seconds: (Date.now() - t0) / 1000, errs }));
if (!/^Pay /.test(payText) || !/^[2-9A-Z]{6}$/.test((bookingCode ?? "").trim())) { console.error("unexpected result"); process.exit(1); }
if (errs.length) { console.error("browser errors:", errs); process.exit(1); }
if (out) await page.screenshot({ path: out });
await browser.close();
