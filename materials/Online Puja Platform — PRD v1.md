# Online Puja Platform — PRD v1

Oct 2, 2026 · @Harsh

## 1. Overview

Build a mobile-first web platform where devotees book a puja or recurring seva at a temple, priests perform the sankalpam in their name and gotra, and every step (confirmation, video proof, prasad shipping) reaches them on WhatsApp. The booking format follows VedaMandir: dated temple pujas, package tiers, WhatsApp proof. Brand, copy, imagery and code are original, and the look is marble and gold.

**Goals for v1**

- A devotee goes from a puja detail page to paid in under 90 seconds on a mid-range Android phone.
- Every booking sends WhatsApp messages at each lifecycle step automatically, through one provider-agnostic layer that runs on Gupshup or WATI.
- Video proof and prasad shipping are tracked per booking on an ops dashboard, against a per-puja SLA.
- Recurring sevas (for example 7 Tuesdays) can be paid in full or by UPI AutoPay.
- Four language storefronts (Telugu, Hindi, Tamil, English), each with its own catalog.

**Non-goals for v1**

- Native mobile apps. The site ships as a PWA.
- Live-streamed darshan. The data model keeps a hook for v2.
- Astrology, panchang, bhajans, consultations.
- A general store. Only prasad and chadhava items tied to a booking are sold.
- A priest-facing app. Temple coordinators upload proof through the admin panel.

**Success metrics** (proposed targets, revisit after 4 weeks of live data)

| Metric | Definition | Target |
| --- | --- | --- |
| Detail to paid conversion | Paid bookings / puja detail sessions | 3% or more |
| Video SLA hit rate | Proof videos delivered within that puja's SLA | 95% or more |
| WhatsApp delivery rate | Delivered / sent, utility templates | 97% or more |
| Refund rate | Refunded / paid bookings | 3% or less |
| Repeat devotees | Devotees with 2+ paid bookings in 90 days | 20% or more |
| Support first reply | WhatsApp first reply in staffed hours | 15 min or less |

**How Claude Code should use this doc**

1. Build milestone by milestone (section 13). A milestone is done when its acceptance checklist passes.
2. Treat the data model (section 9), message templates (section 7) and design tokens (section 11) as source of truth. Ask before deviating.
3. Never hardcode user-facing copy, prices, SLAs, support hours or phone numbers. They come from locale files or the `site_config` table.
4. The brand name is a placeholder, `{{BRAND}}`, set in config until it is chosen.

## 2. Users and core journeys

Three people book on this site, and all three live in WhatsApp. Design for the least technical one first.

| Persona | Who | What they need | Design consequence |
| --- | --- | --- | --- |
| Elderly devotee | 55+, reads Telugu, Hindi or Tamil first, books on a budget Android phone | Trust, large text, someone to ask | 17 px base text, pinch-zoom allowed, WhatsApp and call booking on every puja |
| Family booker | Adult child booking for parents, often from another city | Add several names, pay once, forward proof | Family package, multiple sankalp names, shareable proof link |
| NRI devotee | US, UK, Gulf, Singapore; pays by international card | Foreign currency, time-zone clarity | USD pricing, puja time shown in IST and local time, no Indian-only fields |

**Journey A: one-time puja (the core flow)**

1. Lands on the home page or a puja link shared on WhatsApp or Instagram, in their language.
2. Opens a puja detail page and reads purpose, temple, date and what they will receive.
3. Picks a package: Individual (1 name), Couple (2), Family (up to 4).
4. Fills the sankalp form: names, gotra (with an "I don't know" option), optional nakshatra and wish, WhatsApp number.
5. Optionally adds chadhava offerings and prasad delivery. Prasad needs a shipping address.
6. Logs in by OTP on that WhatsApp number at the payment step, not before.
7. Pays by UPI, card or netbanking.
8. Gets a WhatsApp confirmation with booking ID within 60 seconds.
9. Gets a reminder the evening before, and a "your puja is starting" message on the day.
10. Gets the proof video link within the puja's SLA.
11. If prasad was added, gets shipped and delivered messages with tracking.
12. Gets a feedback request 2 days after the video.

**Journey B: recurring seva**

Same as A, but at checkout the devotee picks Full payment (all occurrences now) or UPI AutoPay (charged before each occurrence). Each occurrence gets its own reminder, proof video and status in My Bookings. The devotee can cancel remaining occurrences from My Subscriptions in two taps.

**Journey C: assisted booking**

The devotee taps Book via WhatsApp or Book via Call. A support agent creates the booking in the admin panel and sends a payment link over WhatsApp. From payment onward the booking follows Journey A.

## 3. Tech stack and architecture

Next.js storefront and admin, a FastAPI backend with a job worker, Postgres, and three swappable provider adapters: messaging, payments, shipping. Every third party sits behind an interface, so moving from WATI to Gupshup, or Razorpay to Cashfree, is a config change.

| Layer | Choice | Notes |
| --- | --- | --- |
| Storefront + admin | Next.js (latest stable, App Router, TypeScript), next-intl, Tailwind CSS | SSR/ISR on every public page; `/admin` is a protected route group in the same app |
| API | FastAPI (Python 3.12), SQLAlchemy 2, Alembic, Pydantic v2 | REST, JSON; OpenAPI spec generates the TS client |
| Database | PostgreSQL 16 | Money stored as integer minor units plus currency code |
| Jobs | Redis + Arq worker | Reminders, scheduled sends, webhook processing, retries with backoff |
| Images | Cloudflare R2 + image resizing | WebP/AVIF, served from a custom CDN domain |
| Proof videos | Cloudflare Stream | Signed playback URLs, HLS; source file kept in R2 |
| WhatsApp | Gupshup or WATI via `MessagingProvider` | Selected by `MESSAGING_PROVIDER` env var |
| Payments | Razorpay (default) or Cashfree via `PaymentProvider` | One-time orders, UPI AutoPay mandates, refunds |
| Shipping | Shiprocket via `ShippingProvider` | Prasad and chadhava item delivery, tracking webhooks |
| Login OTP | WhatsApp authentication template; SMS fallback | OTP to the same number the booking uses |
| Observability | Sentry, PostHog, structured JSON logs | Every outbound message and webhook logged with booking ID |

**Repo layout** (pnpm workspaces for TS, uv for Python)

```text
/apps
  /web            Next.js storefront + /admin
  /api            FastAPI app (routers, services, models)
    /providers
      /messaging  base.py, gupshup.py, wati.py, fake.py
      /payments   base.py, razorpay.py, cashfree.py, fake.py
      /shipping   base.py, shiprocket.py, fake.py
  /worker         Arq worker entrypoint (imports api services)
/packages
  /ui             design tokens + React components (section 11)
  /locales        te.json, hi.json, ta.json, en.json
/infra            docker-compose (postgres, redis), seed data
```

Each provider folder ships a `fake` adapter that records calls to a table. Local dev and CI run on fakes; no test ever hits a real BSP, gateway or courier.

**Environment variables**

```text
DATABASE_URL, REDIS_URL, JWT_SECRET, NEXT_PUBLIC_SITE_URL, REVALIDATE_SECRET
R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL
CF_STREAM_ACCOUNT_ID, CF_STREAM_API_TOKEN, CF_STREAM_SIGNING_KEY_ID, CF_STREAM_SIGNING_KEY_PEM
MESSAGING_PROVIDER=gupshup|wati|fake
GUPSHUP_API_KEY, GUPSHUP_APP_NAME, GUPSHUP_SOURCE_NUMBER, GUPSHUP_WEBHOOK_TOKEN
WATI_API_ENDPOINT, WATI_ACCESS_TOKEN, WATI_WEBHOOK_TOKEN
PAYMENT_PROVIDER=razorpay|cashfree|fake
RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET
CASHFREE_APP_ID, CASHFREE_SECRET_KEY, CASHFREE_WEBHOOK_SECRET
SHIPPING_PROVIDER=shiprocket|fake
SHIPROCKET_EMAIL, SHIPROCKET_PASSWORD, SHIPROCKET_PICKUP_LOCATION
SMS_OTP_PROVIDER, SMS_OTP_API_KEY
SENTRY_DSN, POSTHOG_KEY
```

Caching rule: listing pages revalidate every 60 seconds. Detail pages revalidate on demand when the admin publishes a change, plus automatically at each puja's booking cutoff.

&#91;embedded content: system architecture · web, API, worker, four adapters\]

The browser only talks to the Next.js app, and the app only talks to the API. The API and worker reach third parties only through adapters, and every webhook comes back into the API.

## 4. Information architecture and routes

Every public URL carries its locale, every public page is server-rendered, and no link anywhere drops the locale. This fixes VedaMandir's biggest bug: its mobile nav and footer sent users back to the default language.

| Route | Page | Rendering |
| --- | --- | --- |
| `/{locale}` | Home | ISR, 60 s |
| `/{locale}/pujas` | Puja listing; filters as query params `?deity=&dosha=&benefit=&temple=&date=` | ISR, 60 s |
| `/{locale}/pujas/{id}-{slug}` | Puja detail | ISR, on-demand revalidate |
| `/{locale}/sevas` | Seva listing, tabs Daily / Weekly / Monthly | ISR, 60 s |
| `/{locale}/sevas/{id}-{slug}` | Seva detail | ISR, on-demand revalidate |
| `/{locale}/temples/{id}-{slug}` | Temple page: about, photos, all pujas there | ISR |
| `/{locale}/checkout/{draftId}` | Sankalp form, add-ons, payment | Client, no-index |
| `/{locale}/bookings/{id}/success` | Confirmation | Client, no-index |
| `/{locale}/account` | Profile, saved family members, language | Client, auth |
| `/{locale}/account/bookings/{id}` | Booking timeline, proof video, invoice | Client, auth |
| `/{locale}/account/subscriptions` | Recurring sevas, cancel or pause | Client, auth |
| `/{locale}/proof/{token}` | Shareable proof page: video, puja, temple, date | SSR, no-index, unguessable token |
| `/{locale}/about`, `/faq`, `/contact` | Static content | SSG |
| `/{locale}/legal/{terms,privacy,refunds,shipping}` | Legal pages | SSG |
| `/{locale}/account/delete` | Account deletion request | Client, auth |
| `/sitemap.xml`, `/robots.txt` | Generated from the database | Route handlers |
| `/admin/*` | Admin panel (section 10) | Client, staff auth |

**Locale rules**

- Locales are `te`, `hi`, `ta`, `en`, always ISO 639-1. `/` redirects to the cookie locale, else `Accept-Language`, else `en`.
- First visit with no cookie shows a full-screen language picker: four large buttons, each written in its own script.
- All internal links go through one locale-aware `Link` component. An ESLint rule bans raw internal `<a href="/...">`.
- Each locale has its own catalog. A puja exists in a locale only if it has a published translation row for it.
- The language switcher keeps the user on the same page if it exists in the target locale. Otherwise it goes to that locale's listing.
- Every page emits `hreflang` alternates for the locales it exists in, plus `x-default`.

**SEO requirements**

- Each page has its own title, meta description, canonical and OG image (1200x630, generated from the puja hero).
- JSON-LD: `Organization` on home, `Event` on dated pujas (with `Place` and `Offer`), `FAQPage` where FAQs render, `BreadcrumbList` everywhere.
- The admin blocks publishing if any meta field or template variable would render empty.
- Staging runs behind basic auth with `noindex`, on a host never linked from production.
- No `notranslate` meta tag, and the viewport allows zoom.

## 5. Feature specs

Seven surfaces make up v1: home, puja listing, puja detail, seva detail, chadhava, checkout and account, with support woven through all of them. Section order on each page is fixed below; copy comes from locale files.

### 5.1 Global chrome

- **Header:** logo, nav (Pujas, Sevas, Temples), language switcher, "Need help? WhatsApp" button.
- **Mobile bottom tab bar** on every page and every locale: Home, Pujas, Sevas, Account. All four tabs keep the current locale.
- **Footer:** about, FAQ, contact, legal links, social links, one support phone and one WhatsApp number. The number displayed is the number linked.

### 5.2 Home page (top to bottom)

1. Hero carousel: up to 5 admin-picked pujas. Each slide has an occasion chip, title, subtitle, image in a gold arch frame and a "Book puja" button. Auto-advance every 6 s, pause on touch, swipeable.
2. Trust bar: three numbers from live data (pujas completed, devotees served, average rating with review count), each with an "as of" date. A number is hidden until it passes a threshold set in config.
3. Promise strip: sankalp in your name and gotra; performed at the listed venue; proof video within {video\_sla\_hours} hours; verified priests. Values come from `site_config`.
4. How it works: four steps (choose puja, enter names and gotra, puja performed, receive video and blessings).
5. Upcoming pujas: chip tabs (All, Deity, Dosha, Benefit), 6 cards, "View all pujas".
6. Recurring sevas: 3 cards.
7. Temples: horizontal scroll of temple cards.
8. Gallery: real photos from completed pujas, each captioned with temple and date.
9. Testimonials: only reviews from completed bookings. Show first name, city and the puja reviewed.
10. FAQ accordion, 8 questions per locale from the CMS.
11. Closing call-to-action band, then footer.

### 5.3 Puja listing

- Filter chips: Deity, Dosha, Benefit, Temple, Date (this week, next week, festival). On mobile they open a bottom sheet with Apply and Clear. Filters sync to the URL.
- Sort: Soonest (default), Price low to high, Most booked.
- Search across title, temple and deity in the current locale (Postgres trigram).
- Card: image, occasion chip, title clamped to 2 lines, temple and city, weekday and date, "from ₹501", "Book" button.
- "Load more" button, 12 cards per page; end state reads "You've seen all N pujas".
- A puja disappears from listings at its booking cutoff, automatically.

### 5.4 Puja detail (top to bottom)

1. Image gallery, swipeable, up to 6 images, alt text required.
2. Title block: occasion chip, H1, subtitle, temple (links to temple page), city, venue-type badge (Temple, Yagashala, Ghat, Kund), date and time in IST plus the visitor's local time when it differs.
3. Booking countdown: shown only when the real `booking_cutoff_at` is under 72 hours away. Never shown otherwise.
4. Package selector as radio cards: Individual (1 name), Couple (2), Family (up to 4), each with its price and the number of names it includes.
5. Primary button "Book this puja", plus "Book on WhatsApp" and "Call to book". On mobile a sticky bottom bar shows the selected package, price and button.
6. Promise strip, using this puja's SLA if it overrides the default.
7. Sticky section nav: About, Benefits, Rituals, Temple, You will receive, Reviews, FAQ.
8. About: rich text, collapsed after 6 lines with "Read more".
9. Fact box: tradition, duration, number of priests, sankalp language. All required in the CMS, no defaults.
10. Benefits: title + one line each, written as the ritual's traditional purpose.
11. Rituals: numbered steps; at most one flagged "main ritual".
12. Temple: name, presiding deity, city and state, short history, map link, photos.
13. You will receive: generated from the puja's deliverables (sankalp video, full video, photos, prasad if added), with the same SLA hours as the badge.
14. Chadhava add-ons preview, if the puja has any.
15. Reviews from verified bookings of this puja or temple.
16. FAQ: puja-specific, then global.
17. Recommendations: 4 upcoming pujas with the same deity or benefit.
18. Help box: "Not sure which puja to book?" with a WhatsApp button.

Wishlist (heart) works logged out in local storage and syncs on login. Share uses the Web Share API, falling back to a WhatsApp share link with localized prefilled text.

### 5.5 Seva detail

Same layout as puja detail, with two additions.

- **Schedule block:** recurrence ("Every Tuesday, 7 weeks"), first date, and the full list of dates.
- **Payment choice** at the package step: "Full payment: ₹X once" or "UPI AutoPay: ₹Y before each Tuesday". Show the total for both. Full payment is the default; nothing is pre-selected as "Recommended" unless it is cheaper.

Each occurrence gets its own reminder, proof video and status line.

### 5.6 Chadhava (offerings)

- Two forms: a standalone chadhava listing (for example "Shani chadhava, choose your offerings"), or add-ons attached to a puja.
- Each item has a name, image, price, max quantity and a `ships_home` flag. Items placed at the shrine appear in the proof video; items with `ships_home` are couriered.
- UI: item grid with a quantity stepper and a running total in the sticky bar.

### 5.7 Checkout (three steps, one page on desktop)

1. **Sankalp details.** One block per name slot in the package: full name (required), relation (optional). Gotra field with suggestions and an "I don't know my gotra" checkbox; the fallback gotra comes from config and is shown to the user. Nakshatra select (optional; required when the puja sets `requires_nakshatra`). Wish, optional, 140 characters. WhatsApp number with country code, default +91. Option to save these people to the profile.
2. **Add-ons.** Chadhava items, prasad delivery (address form with pincode serviceability check), optional dakshina chips.
3. **Review and pay.** Price breakdown (package, add-ons, shipping, tax if applicable), WhatsApp updates consent (required, with one line explaining proof is delivered there), terms consent. OTP login happens here if needed. Pay opens the gateway checkout.

Rules: no pre-ticked paid add-ons; the total shown before payment equals the amount charged. The success page shows the booking ID, a "what happens next" timeline and an add-to-calendar file.

### 5.8 Account

- **Login:** phone + OTP over WhatsApp, SMS fallback after 30 s. Session in an httpOnly cookie, 90 days.
- **Profile:** name, optional email, language, default WhatsApp number.
- **Family members:** saved names with gotra, nakshatra and relation, picked in one tap at checkout.
- **My Bookings:** list with status chips. Booking detail shows a timeline (Paid, Scheduled, Performed, Video sent, Shipped, Delivered), the proof video player, photos, invoice PDF, "Book again" and a support button prefilled with the booking ID.
- **My Subscriptions:** each active seva with next date, payment mode and mandate status. "Cancel remaining dates" is one screen and one confirmation.
- **Wishlist** and **Delete account** (request flow, confirmation message, completed within 30 days).

### 5.9 Support and reviews

- The WhatsApp help button is prefilled per locale with page context, for example the puja title.
- "Call to book" shows only within staffed hours from config. Outside them it becomes a callback request form.
- Inbound WhatsApp is handled in the BSP's own team inbox in v1. Our webhook logs each inbound message against the devotee's latest booking.
- Two days after the proof video, a WhatsApp message asks for a 1 to 5 rating via quick-reply buttons, then optional text. Reviews show on the site after moderation.

## 6. Booking lifecycle and fulfilment

A booking moves through a fixed state machine, and every transition is a database event that can send a WhatsApp message. Shipments run as a separate sub-machine, so a booking without prasad never waits on a courier.

&#91;embedded content: booking state machine · 8 states on the main path, 3 exceptions\]

The normal path runs top to bottom. Only a cancellation before cutoff or a disrupted event leads to a refund.

| State | Entered when | Set by | WhatsApp template (section 7) |
| --- | --- | --- | --- |
| `draft` | Checkout opened | System | none |
| `pending_payment` | Pay pressed, gateway order created | System | none |
| `confirmed` | Payment webhook verified | System | `booking_confirmed` |
| `locked` | Event booking cutoff passes; names frozen | Scheduler | none |
| `performed` | Coordinator marks the event performed | Ops | `puja_started` (sent earlier, when the coordinator tapped Started) |
| `proof_ready` | This booking's clip is cut and passes QC | Worker + ops | none |
| `proof_sent` | Proof message accepted by the BSP | Worker | `proof_video` |
| `completed` | Proof sent and shipment delivered (or no shipment) | System | `feedback_request` (+2 days) |
| `cancelled` | Devotee cancels before cutoff, or event cancelled | Devotee / ops | `booking_cancelled` |
| `refunded` | Refund webhook confirms | System | `refund_processed` |
| `rescheduled` | Event moved to a new date | Ops | `puja_rescheduled` (with Accept / Refund buttons) |

Shipment states: `pending`, `packed`, `shipped`, `out_for_delivery`, `delivered`, `returned`. Templates: `prasad_shipped`, `prasad_out_for_delivery`, `prasad_delivered`.

**Events and the sankalp sheet**

- Bookings attach to a `puja_event` (one date and time of one puja at one venue). Recurring sevas create one event per occurrence.
- At cutoff the system builds the sankalp sheet: every locked booking's names, gotra, nakshatra and wish, transliterated into the sankalp language and numbered. It renders as a mobile view and a printable PDF for the priest.
- Edits to names are allowed until cutoff, then only by ops.

**Proof videos, built to scale to hundreds of names per event**

1. The coordinator records the sankalp as one continuous video while the priest reads the sheet in order, plus a separate full-ritual video.
2. Both upload from the admin panel (resumable upload to R2, then ingest to Cloudflare Stream).
3. In the marker tool the coordinator plays the sankalp video and taps "Next name" as each booking's sankalp begins. Each tap stores a start timestamp against the next booking on the sheet.
4. The worker cuts one clip per booking with ffmpeg, from its marker to the next one plus 2 seconds.
5. QC: the coordinator spot-checks at least 1 in 10 clips (and every clip under 5 seconds) before approving the batch.
6. On approval each booking moves to `proof_ready` and the worker sends `proof_video`.

Fallback for small events: bulk-upload individual clips named `{booking_code}.mp4`, matched automatically.

**SLA tracking**

- Each event stores `video_sla_hours` (default from `site_config`). This one number drives the badge, the "You will receive" text and the dashboard.
- The ops dashboard lists bookings at risk (6 hours before breach) and breached.
- A breach alerts ops by email and Slack, and sends the devotee `proof_delayed` with a new ETA. It never fails silently.

**Disrupted events**

If an event cannot happen (temple closure, priest unavailable), ops marks it disrupted and chooses one action for all its bookings: reschedule to a new date, where each devotee gets Accept or Refund buttons and no reply in 48 hours means accept; or refund all.

**Prasad shipping**

- Each puja defines its prasad box contents. Shelf-stable items only: dry prasad, kumkum, vibhuti, akshata, raksha sutra.
- After the event, ops creates shipments in bulk. The adapter books them with Shiprocket, stores the AWB and prints labels.
- Tracking webhooks update shipment state and trigger the shipping templates.
- India addresses only in v1. The prasad option is hidden when the address country is not India.

## 7. WhatsApp messaging layer

All WhatsApp traffic goes through one `MessagingProvider` interface with a WATI adapter and a Gupshup adapter. Templates are defined once in our database and mapped to each provider's template name or ID. Recommendation: launch on WATI, because its team inbox covers assisted booking and support with no extra build; keep Gupshup as the switch if its per-message quote is lower at volume.

**Interface** (`apps/api/providers/messaging/base.py`)

```python
class MessagingProvider(Protocol):
    async def send_template(
        self, to: str, template: TemplateRef, params: list[str],
        header_media_url: str | None = None,
        button_params: list[str] | None = None,
        idempotency_key: str = "",
    ) -> SendResult: ...          # provider_message_id, accepted: bool, error

    async def send_session_text(self, to: str, text: str) -> SendResult: ...
    # only inside an open 24-hour customer service window

    def parse_webhook(self, headers: dict, body: bytes) -> list[MessagingEvent]: ...
    # normalised: sent | delivered | read | failed(code) | inbound_text | inbound_button(payload)

    async def list_templates(self) -> list[ProviderTemplate]: ...
```

**How each adapter maps to its provider**

| Concern | WATI | Gupshup |
| --- | --- | --- |
| Send template | `POST {WATI_API_ENDPOINT}/api/v2/sendTemplateMessage?whatsappNumber=` with JSON `template_name`, `broadcast_name`, `parameters` | `POST https://api.gupshup.io/wa/api/v1/template/msg`, form-encoded `source`, `src.name`, `destination`, `template={"id","params"}` |
| Auth | `Authorization: Bearer <token>` | `apikey` header |
| Template key | Template name | Template ID (UUID) |
| Tracking ID | `localMessageId` in the response | `messageId` in the response |
| Status webhooks | `templateMessageSent_v2`, `sentMessageDELIVERED_v2`, `sentMessageREAD_v2`, `templateMessageFailed` | Message-event callbacks set in the app dashboard; confirm payload shape against Gupshup docs |
| Inbound | `messageReceived` | Inbound message callback |

Sources: [WATI send template](https://docs.wati.io/reference/sendtemplatemessage), [WATI webhooks](https://support.wati.io/en/articles/11463225-how-to-track-template-message-delivery-and-message-status-using-wati-webhooks), [Gupshup template messages](https://docs.gupshup.io/docs/template-messages), [Gupshup text template reference](https://docs.gupshup.io/reference/sending-text-template).

**Templates** (each approved in te, hi, ta and en; sent in the booking's locale)

| Key | Category | Trigger | Variables | Buttons |
| --- | --- | --- | --- | --- |
| `otp_login` | Authentication | Login request | code | Copy code |
| `booking_confirmed` | Utility | Payment verified | name, puja, temple, date and time IST, package, booking code | URL: view booking |
| `payment_link` | Utility | Agent creates assisted booking | name, puja, amount, expiry | URL: pay |
| `puja_reminder` | Utility | 18:00 local the day before | name, puja, temple, date and time | none |
| `puja_started` | Utility | Coordinator taps Started in admin | puja, temple | none |
| `proof_video` | Utility | Booking reaches `proof_ready` | name, puja, temple, date | Header: personal sankalp clip; URL: full proof page |
| `proof_delayed` | Utility | SLA breach | puja, new ETA | none |
| `prasad_shipped` | Utility | Shipment picked up | puja, courier, AWB | URL: track |
| `prasad_out_for_delivery` | Utility | Courier event | courier, AWB | URL: track |
| `prasad_delivered` | Utility | Courier event | puja | none |
| `booking_cancelled` | Utility | Cancellation | puja, booking code, refund amount | none |
| `refund_processed` | Utility | Refund webhook | amount, reference, expected days | none |
| `puja_rescheduled` | Utility | Event disrupted, rescheduled | puja, old date, new date | Quick replies: Accept, Refund |
| `seva_predebit` | Utility | 26 hours before each AutoPay debit | seva, amount, date, mandate reference | URL: manage |
| `seva_payment_failed` | Utility | Debit fails | seva, date, amount | URL: pay now |
| `feedback_request` | Meta decides at approval (often marketing) | 2 days after proof | name, puja | Quick replies: 1 to 5 |
| `checkout_reminder` | Marketing | 1 hour after an abandoned checkout, marketing opt-in only | name, puja | URL: resume |
| `festival_offer` | Marketing | Campaign from admin, marketing opt-in only | festival, puja | URL: book |

**Proof video delivery**

- WhatsApp caps video at 16 MB and needs H.264 video with AAC audio ([Meta media reference](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media)). A full ritual video never fits.
- So each devotee's personal sankalp clip (usually 20 to 60 s) is transcoded to 720p H.264/AAC. If it lands at 15 MB or less, it goes as the template's header video, so elderly users see their own names being read without opening a link.
- The URL button always opens `/{locale}/proof/{token}`: the clip, the full ritual video from Cloudflare Stream, photos, puja, temple and date. The page is shareable but not indexed.
- If the clip is over 15 MB, the header falls back to a thumbnail image (JPEG, 5 MB or less).

**Sending rules**

- **Idempotency:** `message_log` has a unique key on (booking, template, occurrence). The worker checks it before sending, so a retried job never double-sends.
- **Retries:** timeouts and 5xx retry 3 times with exponential backoff. A `failed` webhook for an invalid number puts the booking into the ops call queue.
- **Quiet hours:** nothing except OTPs goes out between 21:30 and 07:30 in the recipient's time zone. Held messages send at 07:30.
- **Consent:** checkout records a WhatsApp-updates consent (timestamp, consent text version). Marketing consent is a separate, unticked checkbox.
- **Opt-out:** an inbound "STOP" removes marketing consent. Utility messages for active bookings continue.
- **Template copy:** factual about the ritual, no promised outcomes. Meta re-categorises utility templates that read as promotional, and marketing costs about 7.5 times more.

**Cost per booking** (Meta's India rates; BSP markup and 18% GST extra)

Meta charges per delivered template message since July 1, 2025 ([Meta pricing](https://developers.facebook.com/docs/whatsapp/pricing)). Utility templates sent inside an open 24-hour customer service window are free. India list rates are ₹0.8631 for marketing and ₹0.115 for utility and authentication ([ChatMitra rate summary](https://chatmitra.com/blog/whatsapp-business-cost-per-message/)). BSPs report that from October 1, 2026 free-form service replies are billed at ₹0.115 beyond 1,000 free per number each month; verify on Meta's rate card before launch.

A one-time booking with prasad sends about 1 authentication and 8 utility templates: roughly ₹1.04 in Meta fees before markup and GST. That is about 0.2% of a ₹501 booking.

## 8. Payments

Razorpay is the default gateway behind a `PaymentProvider` interface, with a Cashfree adapter alongside; use whichever merchant account is approved first. One-time orders, UPI AutoPay mandates, refunds and international cards all go through the interface. Only a signature-verified webhook confirms a payment, never the browser redirect.

**Interface** (`apps/api/providers/payments/base.py`)

```python
class PaymentProvider(Protocol):
    async def create_order(self, booking_id: str, amount_minor: int, currency: str,
                           customer: Customer, notes: dict) -> OrderRef: ...
    async def create_mandate(self, subscription_id: str, max_amount_minor: int,
                             frequency: str, start_at: datetime, end_at: datetime,
                             customer: Customer) -> MandateRef: ...
    async def charge_mandate(self, mandate_token: str, amount_minor: int,
                             idempotency_key: str) -> ChargeRef: ...
    async def cancel_mandate(self, mandate_token: str) -> None: ...
    async def refund(self, payment_id: str, amount_minor: int, reason: str,
                     idempotency_key: str) -> RefundRef: ...
    def verify_webhook(self, headers: dict, body: bytes) -> list[PaymentEvent]: ...
```

**One-time payment**

1. The server prices the booking (package, add-ons, shipping) and creates the gateway order. Client-sent prices are ignored.
2. The client opens the gateway checkout with the order ID.
3. The `payment.captured` webhook, verified by HMAC signature, moves the booking to `confirmed`. The return page shows "Confirming your booking" and polls status.
4. Unpaid orders expire after 30 minutes and the draft is released.

**Recurring sevas**

- **Full payment:** one order covering every occurrence.
- **UPI AutoPay:** a mandate is registered at checkout together with the first debit. Frequency is weekly (or "as presented"). The mandate's max amount equals the per-occurrence price. Keep it at ₹15,000 or less: above that, every debit needs the devotee's UPI PIN ([Razorpay UPI Autopay](https://razorpay.com/docs/payments/payment-gateway/s2s-integration/recurring-payments/upi/?preferred-country=US)).
- **Debit schedule per occurrence** (T = puja time): the gateway's pre-debit notice and our `seva_predebit` WhatsApp go out at T minus 50 h; the debit runs at T minus 25 h; the booking cutoff is T minus 12 h. RBI requires the pre-debit notice at least 24 hours before each debit ([Razorpay on pre-debit notices](https://razorpay.com/blog/is-autopay-safe-upi-security-guide/)).
- **Failed debit:** send `seva_payment_failed` with a pay-now link. If still unpaid at cutoff, that occurrence is skipped (no puja, no charge) and the next one proceeds.
- **Cancel:** one tap in My Subscriptions cancels the mandate through the API and cancels future occurrences. It must be as easy as signing up.

**Cancellation and refunds** (one policy, stored in `site_config`, shown identically everywhere)

- Free cancellation until the booking cutoff (default 12 hours before the puja, set per event). After cutoff, no cancellation, because the sankalp sheet is printed.
- Full refund if we cannot perform the puja, if the devotee picks Refund on a rescheduled event, or if proof is not delivered within 7 days of the SLA.
- Partial refund for add-ons we could not ship (for example, an unserviceable pincode).
- Refunds go to the original payment method. The devotee gets `refund_processed` with the reference and expected days.
- Full-payment sevas cancelled mid-way refund every occurrence whose cutoff has not passed.

**NRI and international**

- Each package stores an INR price and a USD price, set by hand, not live-converted.
- Visitors outside India see USD by default and can switch currency. UPI is hidden for USD orders; international cards are enabled on the gateway.
- Prasad delivery is India-only in v1.

**Invoices and reconciliation**

- Every paid booking gets an invoice PDF in My Bookings and the admin panel.
- A daily job pulls gateway settlements, matches them to bookings and flags mismatches in the admin finance view.
- GST treatment of puja services, platform fees and prasad is an open question for a chartered accountant (section 13). Build the invoice to show tax lines driven by config, defaulting to none.

## 9. Data model

Twenty-odd Postgres tables, grouped below. Content that varies by language lives in `*_translations` tables keyed by (entity, locale); everything else is language-neutral. Money is integer minor units with a currency code, and times are `timestamptz` in UTC.

```sql
-- People
users(id, phone_e164 UNIQUE, name, email, locale, whatsapp_opt_in_at,
      marketing_opt_in_at, deleted_at, created_at)
family_members(id, user_id FK, name, relation, gotra, nakshatra)
staff_users(id, email UNIQUE, name, role ENUM(admin, catalog_editor,
      ops_coordinator, support_agent, finance), totp_secret, active)

-- Catalog
temples(id, slug, city, state, lat, lng, presiding_deity,
      venue_type ENUM(temple, yagashala, ghat, kund), photos JSONB)
temple_translations(temple_id FK, locale, name, address, history_md,
      PRIMARY KEY(temple_id, locale))
pujas(id, temple_id FK, kind ENUM(one_time, seva, chadhava),
      deity_tags TEXT[], dosha_tags TEXT[], benefit_tags TEXT[],
      tradition NOT NULL, duration_minutes NOT NULL, priests_count NOT NULL,
      sankalp_language NOT NULL, requires_nakshatra BOOL,
      video_sla_hours INT NULL,          -- null = site default
      deliverables JSONB NOT NULL,       -- ["sankalp_clip","full_video","photos"]
      prasad_box JSONB NULL, status ENUM(draft, published, archived))
puja_translations(puja_id FK, locale, title, subtitle, occasion_chip,
      about_md, benefits JSONB, rituals JSONB, faqs JSONB,
      meta_title, meta_description, published BOOL,
      PRIMARY KEY(puja_id, locale))
packages(id, puja_id FK, code ENUM(individual, couple, family),
      max_names INT, price_inr_minor INT, price_usd_minor INT, active)
addon_items(id, puja_id FK NULL, image_key, price_inr_minor, price_usd_minor,
      max_qty, ships_home BOOL, active)
addon_item_translations(addon_item_id FK, locale, name, description)
seva_plans(id, puja_id FK, rrule TEXT, occurrences INT, autopay_allowed BOOL)
puja_events(id, puja_id FK, starts_at, booking_cutoff_at, video_sla_hours,
      status ENUM(scheduled, started, performed, disrupted, cancelled),
      sankalp_sheet_key, sankalp_video_stream_id, full_video_stream_id)

-- Bookings
bookings(id, code UNIQUE,              -- short human code, e.g. 7K3Q9M
      user_id FK, puja_event_id FK, package_id FK, subscription_id FK NULL,
      locale, currency, subtotal_minor, addons_minor, shipping_minor,
      tax_minor, total_minor, status ENUM(...section 6...),
      whatsapp_e164, wish, consent_whatsapp_at, consent_text_version,
      proof_token UNIQUE, created_at, confirmed_at, cancelled_at)
booking_names(id, booking_id FK, position, name, relation, gotra,
      gotra_unknown BOOL, nakshatra)
booking_addons(booking_id FK, addon_item_id FK, qty, unit_price_minor)
subscriptions(id, user_id FK, seva_plan_id FK, package_id FK,
      payment_mode ENUM(full, autopay), mandate_id FK NULL,
      status ENUM(active, cancelled, completed, mandate_failed),
      next_occurrence_at)

-- Money
payments(id, booking_id FK NULL, subscription_id FK NULL, provider,
      provider_order_id, provider_payment_id, amount_minor, currency,
      status, raw JSONB)
mandates(id, subscription_id FK, provider, token, max_amount_minor,
      frequency, status)
refunds(id, payment_id FK, amount_minor, reason, provider_refund_id, status)

-- Fulfilment
proof_clips(id, booking_id FK, puja_event_id FK, start_ms, end_ms,
      stream_id, r2_key, size_bytes,
      qc_status ENUM(pending, approved, rejected), sent_inline BOOL)
shipments(id, booking_id FK, address JSONB, provider, provider_order_id,
      awb, courier, tracking_url,
      status ENUM(pending, packed, shipped, out_for_delivery, delivered, returned),
      events JSONB)

-- Messaging
message_templates(key, locale, category, provider, provider_template_ref,
      variables TEXT[], status, PRIMARY KEY(key, locale, provider))
message_log(id, booking_id FK NULL, user_id FK, template_key, occurrence_key,
      to_e164, provider, provider_message_id,
      status ENUM(queued, sent, delivered, read, failed), error_code,
      created_at, UNIQUE(booking_id, template_key, occurrence_key))
inbound_messages(id, from_e164, text, button_payload,
      matched_booking_id FK NULL, received_at)

-- Trust, config, audit
reviews(id, booking_id FK UNIQUE, rating INT, text, locale,
      status ENUM(pending, approved, rejected))
site_config(key PRIMARY KEY, value JSONB)
webhook_events(id, provider, event_type, idempotency_key UNIQUE, payload JSONB,
      received_at, processed_at, error)
audit_log(id, actor_staff_id, action, entity, entity_id, diff JSONB, at)
```

**`site_config` keys** (the single source for every promise on the site): `video_sla_hours_default`, `booking_cutoff_hours_default`, `support_hours`, `support_languages`, `support_phone_e164`, `whatsapp_number_e164`, `gotra_fallback` (per locale), `trust_bar_thresholds`, `quiet_hours`.

## 10. Admin panel

The admin panel at `/admin` runs the business: catalog, daily temple operations, bookings, shipping, messaging and money. Ops screens must work on a phone, because coordinators use them at the temple.

**Roles**

| Role | Can do |
| --- | --- |
| Admin | Everything, including staff, roles and site config |
| Catalog editor | Temples, pujas, translations, packages, add-ons, events, media |
| Ops coordinator | Today's events, sankalp sheets, uploads, marker tool, QC, shipping |
| Support agent | Booking lookup, assisted booking, resend messages, edit names before cutoff |
| Finance | Payments, refunds, reconciliation, exports |

Staff sign in with email, password and TOTP. Sessions last 12 hours. Every write lands in `audit_log`.

**Modules**

1. **Catalog CMS.** Temples, pujas, packages, add-ons, seva plans. One tab per locale with a side-by-side preview of the real page. Required fields are enforced and publishing is blocked if any meta field or template variable is empty. Publish triggers on-demand revalidation.
2. **Events.** Create one event, or generate a series from a seva's recurrence rule. Each event shows its cutoff, SLA, booking count and status.
3. **Media.** Upload to R2 with alt text required per locale. Images are resized on upload.
4. **Today (ops queue).** Today's events in time order. Per event:
   1. View and print the sankalp sheet.
   2. Tap "Started" (sends `puja_started`).
   3. Upload the sankalp video, full video and photos (resumable).
   4. Run the marker tool, then QC and approve clips.
   5. Tap "Performed".
5. **SLA board.** Bookings at risk (6 hours before breach) and breached, grouped by event, with one-tap reassign or escalate.
6. **Bookings.** Search by code, phone or name. Detail shows the timeline, names, payments, refunds, shipment, and every message with its delivery status. Actions: resend a message, edit names (before cutoff, or after with an audit reason), cancel and refund, add a note.
7. **Assisted booking.** Create a booking for a phone number, generate a payment link and send it with `payment_link`.
8. **Shipping.** Shipments by event, bulk create with the courier, print labels, track status.
9. **Messaging.** Template sync from the provider (approved or rejected status), test send to a staff number, and marketing campaigns to opted-in devotees, segmented by locale and interest. Campaigns are capped at 2 per devotee per week. Delivery and read stats per template.
10. **Reviews.** Approve or reject before anything shows on the site.
11. **Site config.** Edit the keys in section 9, with audit.
12. **Finance.** Payments, refunds, reconciliation mismatches, CSV export.
13. **Audit log** viewer.

## 11. Design system: marble and gold

The look is a temple courtyard at morning light: warm white marble surfaces, thin gold detailing and dark walnut text. Gold is an accent, never a background for reading. Every text colour pair below passes WCAG AA, because the core user is over 55.

**Colour tokens**

| Token | Hex | Use | Contrast |
| --- | --- | --- | --- |
| `marble-50` | #FBF9F5 | Page background | n/a |
| `marble-100` | #F4F0E8 | Alternate section background | n/a |
| `marble-200` | #E7E1D6 | Borders, dividers, vein colour | n/a |
| `marble-400` | #B9B1A4 | Disabled states, muted veins | n/a |
| `surface` | #FFFFFF | Cards ("polished marble") | n/a |
| `ink-900` | #2B2118 | Primary text | about 14:1 on marble-50 |
| `ink-600` | #5E5246 | Secondary text | about 7:1 on marble-50 |
| `gold-100` | #F6EDD0 | Selected chip and row fill | n/a |
| `gold-300` | #EAD9A0 | Highlights, soft gold fills | n/a |
| `gold-500` | #D4AF37 | Primary button background (with ink-900 text) | about 7.5:1 |
| `gold-600` | #B8922E | Button hover, gold hairlines, selected borders | about 5.4:1 with ink-900 |
| `gold-700` | #7A5C17 | Gold text, links and icons on marble | about 5.7:1 on marble-50 |
| `sindoor-600` | #9E2A22 | Errors, destructive actions | about 7:1 on marble-50 |
| `tulsi-600` | #3E6B3A | Success, delivered states | about 5.8:1 on marble-50 |

```css
:root {
  --marble-50:#FBF9F5; --marble-100:#F4F0E8; --marble-200:#E7E1D6; --marble-400:#B9B1A4;
  --surface:#FFFFFF; --ink-900:#2B2118; --ink-600:#5E5246;
  --gold-100:#F6EDD0; --gold-300:#EAD9A0; --gold-500:#D4AF37; --gold-600:#B8922E; --gold-700:#7A5C17;
  --sindoor-600:#9E2A22; --tulsi-600:#3E6B3A;
  /* decorative only: borders, ornaments, display text 32px and up */
  --gold-foil: linear-gradient(135deg,#8C6A1F 0%,#D4AF37 40%,#F3E3A3 55%,#B8922E 75%,#8C6A1F 100%);
  --shadow-card: 0 1px 2px rgba(43,33,24,.06), 0 8px 24px rgba(43,33,24,.08);
  --radius-card:16px; --radius-btn:12px; --radius-chip:999px;
}
```

Map these into the Tailwind theme (`colors.marble`, `colors.gold`, `colors.ink`) in `packages/ui`. No raw hex anywhere else in the codebase.

**Marble and gold treatments**

- **Marble texture:** one original vein texture, a 1200 px WebP tile of 40 KB or less, at 6 to 8% opacity over `marble-50`. Use it behind the hero, section headers and the footer only, never behind paragraphs.
- **Gold hairlines:** 1 px `gold-600` on featured cards and under the sticky book bar.
- **Gold foil:** a 2 px `--gold-foil` border on the selected package card and around arch frames. Also used on display headings of 32 px and up, as gradient text with an `ink-900` fallback.
- **Arch frame:** hero and temple images sit in a temple-arch mask (rounded top rising to a soft point), with a gold-foil stroke. Built with CSS `mask-image` from one SVG path.
- **Ornamental divider:** a thin gold rule with a small original lotus glyph at its centre, between home sections.
- **Shadows:** only `--shadow-card`. No heavy drop shadows, no glassmorphism.

**Typography** (Google Fonts via `next/font`; load only the active locale's script)

| Role | Latin (en) | Telugu (te) | Devanagari (hi) | Tamil (ta) |
| --- | --- | --- | --- | --- |
| Display and headings | Cormorant Garamond 600 | Noto Serif Telugu 600 | Noto Serif Devanagari 600 | Noto Serif Tamil 600 |
| Body and UI | DM Sans 400/500/600 | Noto Sans Telugu | Noto Sans Devanagari | Noto Sans Tamil |

| Style | Size / line height (mobile) | Desktop |
| --- | --- | --- |
| Display | 34 / 40 | 48 / 56 |
| H1 | 28 / 34 | 36 / 44 |
| H2 | 22 / 28 | 28 / 36 |
| H3 | 19 / 26 | 22 / 30 |
| Body | 17 / 27 | 18 / 28 |
| Small | 15 / 22 | 15 / 22 |

Indic scripts get line height 1.7 for body text, because their glyphs are taller. Nothing a user must read goes below 14 px. Cormorant is for display only; it is too thin for body text.

**Layout, spacing and touch**

- 4 px spacing scale. Page gutter 16 px on mobile, 24 px on tablet; content max width 1200 px.
- Every tap target is at least 48 x 48 px. Primary buttons are 52 px tall on mobile.
- Viewport allows pinch zoom. Text respects the browser's font-size setting (`rem` units throughout).

**Buttons**

- **Primary:** `gold-500` background, `ink-900` text, weight 600, a 1 px inner top highlight. Hover is `gold-600`.
- **Secondary:** transparent, 1.5 px `gold-600` border, `gold-700` text.
- **WhatsApp:** white background, official green WhatsApp glyph, `ink-900` text, so older users find it by the icon.
- **Text link:** `gold-700`, underlined.

**Components** (all in `packages/ui`, each with a Storybook story in all four locales)

Header, BottomTabBar, LanguagePicker (full-screen first visit), HeroCarousel, ArchFrame, OrnamentDivider, TrustBar, PromiseStrip, StepsRow, PujaCard, FilterChips with BottomSheet, SearchField, PackageSelector, StickyBookBar, SectionNav, FactBox, BenefitList, RitualSteps, TempleCard, DeliverablesList, AddonGrid with QtyStepper, SankalpNameBlock, GotraField, NakshatraSelect, PriceSummary, Countdown (real deadlines only), Accordion, ReviewCard, ProofPlayer, BookingTimeline, Toast, EmptyState, Skeleton.

**Icons, imagery and motion**

- Line icons at 1.75 px stroke in `gold-700` from an open-licence set (for example Lucide), plus about six custom devotional glyphs (lotus, diya, kalash, temple, bell, conch) drawn for this brand.
- Photos: real photography from partner temples, with written permission, in a warm grade. Deity images are licensed or commissioned; no text or UI is ever placed over a deity's face.
- No images, video or copy taken from other puja platforms.
- Motion: hero crossfade at 400 ms; a gold shimmer on the primary button on desktop hover only. Respect `prefers-reduced-motion`. Video never autoplays with sound.
- Light theme only in v1. Tokens are named so a "black marble" dark theme can be added later without renaming.

## 12. Trust, compliance and quality guardrails

VedaMandir's weakness was not missing features but broken trust: promises that changed page to page, counters that did not add up, and pages in the wrong language. Each problem below becomes a rule with an automated check, so it cannot creep back in.

| Seen on VedaMandir | Our rule | Enforced by |
| --- | --- | --- |
| Video promise of 24, 48 or 72 hours on different pages | One SLA per event, rendered everywhere from data | Copy uses `{video_sla_hours}`; CI fails if a locale file has a literal hour count in proof-related strings |
| Support hours and languages differed per page | One `support_hours` and `support_languages` value | Same token rule in CI |
| Cancellation window of 24 h on some pages, 48 h on others | One cancellation policy in config, read by FAQ, checkout and legal pages | Token rule; legal page renders from config |
| "10L+ devotees", "23L+ pujas" beside 5K app installs | Trust bar shows live database counts, rounded down, with an as-of date, hidden below a threshold | Trust bar has no manual input field in admin |
| Countdown timers server-rendered as 00:00:00 | Countdown only to a real `booking_cutoff_at`, server-rendered with real remaining time | Component takes only an event ID, not a number |
| Telugu strings on English pages, locale lost on navigation | Locale in every URL; every link locale-aware | ESLint rule; CI renders every route per locale and fails if over 2% of visible characters are another locale's script (proper-noun allowlist) |
| "Vaishnava Vedic, Family of 4" on every puja regardless of facts | No CMS defaults; required fields | Publish validation |
| "(Adjust per policy)" in production; staging indexed by Google | No placeholders in published content; staging private | Publish blocks TODO, TBD and bracketed-placeholder patterns; staging has basic auth and `noindex` |
| Same stock gallery on unrelated pujas | Galleries show only real event photos | Each image record requires temple and date taken |
| "Performed in sacred temples" for private yagashalas | Venue type shown on every card and page; promise wording depends on venue type | `venue_type` is required |
| Displayed phone number differed from the linked one | One config value renders both label and link | Single `PhoneLink` component |
| Pinch-zoom disabled | Zoom always allowed | CI check on the viewport meta tag |
| Outcome claims (victory over enemies, court cases) | Copy states the ritual's traditional purpose, never a guaranteed result | Publish blocks a banned-phrase list per locale (guaranteed, 100% result, will remove, and similar) |

**Dark patterns (Consumer Protection Act, CCPA guidelines)**

The CCPA's Guidelines for Prevention and Regulation of Dark Patterns (November 30, 2023) list 13 specified dark patterns ([Fox Mandal summary](https://foxmandal.in/News/consumer-body-notifies-guidelines-on-dark-patterns/)). Penalties have already been imposed for false urgency, drip pricing and basket sneaking ([report](https://www.newkerala.com/news/a/govt-says-ccpa-imposes-rs-20-lakh-dark-948.htm)). The rules that apply here:

- **False urgency:** no fake scarcity, no fake "N people booking now", countdowns only to real cutoffs.
- **Basket sneaking:** no pre-ticked paid add-ons, dakshina or donations.
- **Drip pricing:** shipping and every fee shown before the pay button; charged total equals shown total.
- **Subscription trap:** cancelling a seva or mandate takes the same number of taps as starting it.
- **Confirm shaming:** decline buttons say "No thanks", never guilt copy.

**Personal data (DPDP Act, 2023)**

- Collect only what the sankalp needs: names, gotra, nakshatra, wish, WhatsApp number, plus an address when prasad is ordered.
- Show a purpose notice at checkout. Consent is logged with the text version.
- Account deletion removes or anonymises personal data within 30 days, except records the law requires (invoices).
- Retention of proof videos and sankalp names is an open question (section 13). Build it as config-driven purge jobs.

**Accessibility, performance and security**

- WCAG 2.1 AA. Lighthouse accessibility 95 or more on home, listing, detail and checkout. Form errors are stated in text, not colour alone.
- LCP under 2.5 s on a mid-range Android over 4G. JavaScript under 200 KB gzipped on listing and detail pages. Images as AVIF/WebP, lazy-loaded below the fold.
- Webhooks are verified by signature and deduplicated through `webhook_events`.
- OTP rate limit: 5 per hour per number.
- Admin requires 2FA. Proof tokens are 128-bit random. Secrets are only in env vars.

## 13. Milestones, acceptance criteria and open questions

Six milestones, each shippable to staging on its own. Claude Code builds them in order; a milestone is done only when every box under it is ticked.

**M0. Foundations**: monorepo, CI, Docker Postgres and Redis, design tokens and core components in Storybook, locale routing, language picker, `site_config`, fake providers.

- [ ] All four locales render a styled home shell at `/{locale}`
- [ ] Locale-link ESLint rule and the script-detection CI test exist and pass
- [ ] Storybook shows every token and the core components in all four locales

**M1. Catalog and storefront**: admin catalog CMS, temples, pujas, translations, packages, events, then home, listing, detail and temple pages, SEO (sitemap, robots, JSON-LD, OG images), on-demand revalidation.

- [ ] An editor publishes a puja in Telugu and English, and it appears in both within 60 seconds
- [ ] Publishing is blocked when any required field, meta field or template variable is empty
- [ ] Mobile Lighthouse: performance 90 or more, accessibility 95 or more on home, listing and detail

**M2. Booking and payments**: checkout, OTP login, one-time payments in gateway test mode, webhooks, booking states, My Bookings, cancellations, refunds, invoices.

- [ ] A test-mode booking goes from detail page to `confirmed` end to end
- [ ] Replaying the same payment webhook 5 times confirms the booking once
- [ ] Cancelling before cutoff issues a full refund; after cutoff the option is gone

**M3. WhatsApp**: `MessagingProvider`, WATI adapter, template seeding, every utility trigger, status webhooks, message log in admin, quiet hours, consent and opt-out.

- [ ] A real booking produces `booking_confirmed` on a real phone within 60 seconds
- [ ] Delivered and read statuses show in the admin booking view
- [ ] A forced retry never sends a duplicate message

**M4. Fulfilment**: ops queue, sankalp sheet PDF, uploads, marker tool and ffmpeg clipping, QC, proof page, `proof_video` with inline clip, SLA board, disrupted events, Shiprocket shipping and tracking messages.

- [ ] A 50-name test event is clipped, approved and delivered, each devotee seeing their own clip
- [ ] A simulated SLA breach alerts ops and sends `proof_delayed`
- [ ] Courier tracking events move the shipment and send all three shipping templates

**M5. Sevas and launch**: seva plans, UPI AutoPay mandates, pre-debit messages, My Subscriptions, reviews, Gupshup adapter, analytics, load test, legal pages, go-live checklist.

- [ ] A 3-occurrence test seva on AutoPay debits on schedule with a pre-debit message before each
- [ ] Cancelling the seva stops all future debits in the same number of taps it took to start
- [ ] Setting `MESSAGING_PROVIDER=gupshup` passes the full messaging test suite

**Open questions** (owner: @Harsh)

- [ ] Brand name and domain
- [ ] Which gateway account is approved first: Razorpay or Cashfree?
- [ ] WATI or Gupshup: get per-message quotes at the expected monthly volume
- [ ] Launch locales: all four at once, or Telugu and English first?
- [ ] Partner temples, written permission for photos and video, and who the coordinators are
- [ ] GST treatment of puja services, platform fee and prasad (chartered accountant)
- [ ] Prasad: food-safety licensing, and who packs (temple or a central warehouse)
- [ ] Retention period for proof videos and sankalp names
- [ ] Defaults to confirm: video SLA 48 hours, booking cutoff 12 hours before the puja
- [ ] Live darshan streaming: v2 or never?
