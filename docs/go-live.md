# Go-live checklist

Tick every box before pointing the production domain at Puja Path. Items marked **(owner)** are business decisions from PRD §13's open questions.

## Business decisions (owner)
- [ ] Brand name and domain final (`BRAND`, `NEXT_PUBLIC_SITE_URL`); manifest name updated via `NEXT_PUBLIC_BRAND`
- [ ] Payment gateway account approved (Razorpay or Cashfree); `PAYMENT_PROVIDER` set
- [ ] WhatsApp BSP chosen (WATI or Gupshup) after per-message quotes; `MESSAGING_PROVIDER` set
- [ ] Partner temples signed, with written permission for photos and video; coordinators named and given `ops_coordinator` accounts
- [ ] GST treatment confirmed by a chartered accountant; `tax_rules` in site config set accordingly (default: none)
- [ ] Prasad: food-safety licensing and packer (temple or central warehouse) decided
- [ ] Retention periods for proof videos and sankalp names set in `retention` (purge job reads them)
- [ ] Defaults confirmed: `video_sla_hours_default` (48) and `booking_cutoff_hours_default` (12)
- [ ] Legal pages reviewed by counsel (they render from locale files + site config)

## Content
- [ ] Demo seed catalog removed; real temples, pujas, packages, prices (INR and USD) entered in the CMS
- [ ] Every published puja passes publish validation in each launch locale (the CMS blocks it otherwise)
- [ ] Real event photos uploaded with temple, date taken and alt text in all four languages
- [ ] 8 FAQs per locale reviewed; they use `{video_sla_hours}`-style tokens, never typed numbers
- [ ] Support phone and WhatsApp numbers set in `support_phone_e164` / `whatsapp_number_e164` (one value renders label and link)
- [ ] `support_hours`, `support_languages`, `quiet_hours` set
- [ ] Hero pujas chosen (`hero_puja_ids`)

## WhatsApp
- [ ] All 18 templates submitted and approved in te, hi, ta and en, named `pp_{key}_{locale}`
- [ ] Admin → Messaging → Sync templates shows every template `approved` for the live provider
- [ ] Webhook URL configured at the BSP: `https://<api>/v1/webhooks/messaging/<provider>?token=<WEBHOOK_TOKEN>`
- [ ] Test send of `booking_confirmed` reaches a real phone within 60 seconds (M3 acceptance)
- [ ] Delivered and read statuses appear in Admin → Bookings → messages
- [ ] OTP authentication template approved; SMS fallback provider configured (`SMS_OTP_PROVIDER`)

## Payments
- [ ] Live keys in the secret store (never in the repo); webhook secret set at the gateway
- [ ] Webhook URL: `https://<api>/v1/webhooks/payments/<provider>`; events: payment captured/failed, refund processed/failed, token/subscription status
- [ ] International cards enabled for USD; UPI hidden for USD orders (automatic)
- [ ] UPI AutoPay enabled on the merchant account; per-occurrence prices stay at or under `autopay_max_inr_minor` (₹15,000)
- [ ] One real ₹1 booking + refund end to end in live mode
- [ ] Daily reconciliation job pulls the gateway settlement report (wire `maintenance.reconcile` to the provider's settlement API)

## Shipping
- [ ] Shiprocket pickup location and pincode set; webhook token configured
- [ ] One real shipment booked, label printed, tracking messages received

## Infrastructure
- [ ] Postgres 16 with daily backups and point-in-time recovery; `alembic upgrade head` run
- [ ] Redis for the Arq worker; worker running with at least one replica
- [ ] API behind HTTPS with several uvicorn workers; `APP_ENV=production` (disables `/v1/dev/*` and dev OTP codes)
- [ ] R2 bucket + CDN custom domain (`R2_PUBLIC_BASE_URL`); Cloudflare Stream signing key set
- [ ] `JWT_SECRET` and `REVALIDATE_SECRET` long random values, distinct per environment
- [ ] Staging behind basic auth (`STAGING_BASIC_AUTH`) with `APP_ENV=staging` (noindex everywhere), on a host never linked from production
- [ ] Sentry DSN (`SENTRY_DSN`) for API and web; PostHog key (`NEXT_PUBLIC_POSTHOG_KEY`)
- [ ] Ops alerts: `SLACK_WEBHOOK_URL`, `SMTP_URL`, `OPS_ALERT_EMAIL`; trigger a test SLA breach on staging

## Quality gates (CI must be green)
- [ ] API tests (55) and ruff
- [ ] Locale check, typecheck, ESLint (locale-link rule), Storybook build
- [ ] Script check: every route per locale under 2% foreign script; zoom allowed
- [ ] JS under 200 KB gzipped on listing and detail
- [ ] Lighthouse mobile: performance ≥ 90, accessibility ≥ 95 on home, listing, detail
- [ ] Browser journey: detail page to `confirmed`
- [ ] k6 load test on staging (`infra/loadtest/booking.js`) passes its thresholds

## Admin
- [ ] Bootstrap admin password rotated; every staff member enrolled in 2FA
- [ ] Roles assigned (admin, catalog_editor, ops_coordinator, support_agent, finance)
- [ ] Coordinators have run one full rehearsal on a phone: sheet → Started → upload → marker tool → QC → Performed
