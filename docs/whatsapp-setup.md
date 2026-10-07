# Going live on WhatsApp

Puja Path sends all devotee messages (login codes, confirmations, reminders, puja videos) as WhatsApp
**templates**. Until this is done, `MESSAGING_PROVIDER=fake` records messages instead of sending them.

Allow 1–2 weeks: Meta's business verification is usually the slowest step. Template approval is often minutes to
a day.

## 1. Have these ready

- **A phone number for the business** that can receive an SMS or call, and that is **not** registered on
  WhatsApp (neither the normal app nor WhatsApp Business). If it is, delete that WhatsApp account first.
- **A Meta Business account** at business.facebook.com (create it with your company's legal name).
- **The live website on your own domain**, with its legal pages public (`/en/legal/terms`, `/en/legal/privacy`).
  Meta compares the display name "Puja Path" with the website.
- **Business documents** for verification, e.g. GST certificate, Udyam (MSME) certificate or certificate of
  incorporation, with the same legal name and address as the Meta Business account.

## 2. Choose a provider (one is enough)

| | WATI | Gupshup |
|---|---|---|
| Best for | Small teams: easy dashboard, shared inbox to chat with devotees | Developers: pay as you go, more control |
| Pricing | Monthly plan + Meta's per-message charges | Meta's per-message charges + small markup |
| Template variables | Named: `{{name}}` | Numbered: `{{1}}` |

Check current prices on their sites. Recommendation: **WATI**, because staff also get an inbox to answer devotees
who reply with questions.

## 3. Sign up and connect the number

Everything here happens in the provider's dashboard; its "Connect WhatsApp" button opens Meta's own sign-up window.

1. Create the account on the provider's site and start "Connect WhatsApp".
2. Log in with Facebook and **choose your existing Meta Business account** (don't create a new one). Create the
   WhatsApp Business Account, enter the display name **Puja Path**, and verify the phone number by SMS or call.
   Meta then reviews the display name.
3. **Already verified business? Skip this step.** Otherwise, in **Meta Business Manager → Security Centre**, start
   **Business verification** with your documents. Unverified accounts can message only a small number of people
   per day; verification raises that limit.

Create the templates (step 4) in the provider's dashboard too, not in Meta's WhatsApp Manager. The provider submits
them to Meta for approval and shows the status. WATI's named variables and Gupshup's template IDs, which the app
relies on, only come from templates created there.

## 4. Create the templates

18 message types × 4 languages = 72. You don't type them: a script submits them to Meta from the app's own
definitions, and they then appear in WATI/Gupshup too.

1. In **Meta Business Manager → Users → System users**, create a system user (admin), add your WhatsApp Business
   Account and an app as assets, and generate a token with the `whatsapp_business_management` permission.
2. Note your **WhatsApp Business Account ID** (WhatsApp Manager → Account tools) and, for the video sample,
   the **App ID** of any app in your business.
3. Run it, starting small:

```
cd apps/api
export META_ACCESS_TOKEN=... META_WABA_ID=... META_APP_ID=...
.venv/bin/python scripts/create_templates.py --site https://YOUR-DOMAIN --essential --locales en --video sample.mp4
.venv/bin/python scripts/create_templates.py --site https://YOUR-DOMAIN --video sample.mp4   # everything else later
```

`--dry-run` prints what would be sent. Existing templates are skipped, so it's safe to rerun. With Gupshup, add
`--format positional`. Meta reviews each one, usually within minutes to a day.

### Manual entry (only if you can't use the script)

The full list with exact names, text, sample values and buttons is in `docs/whatsapp-templates.md` (and `.csv`).
First regenerate it with your real domain, because the link buttons use it:

```
cd apps/api && .venv/bin/python scripts/export_templates.py --site https://YOUR-DOMAIN
```

When creating each template in the provider's dashboard:

- **Name** exactly as listed (`pp_booking_confirmed_hi`). The app finds templates by this name.
- **Category** as listed: UTILITY for booking and puja updates, MARKETING for reminders and offers,
  AUTHENTICATION for the login code.
- **Language** as listed: en, hi, ta, te.
- **Body:** copy the "WATI" or "Gupshup" version, according to your provider.
- **Sample values:** Meta requires an example for every variable. Use the ones listed.
- **Buttons:**
  - *Visit website (dynamic URL):* URL `https://YOUR-DOMAIN/{{1}}` with the label listed.
  - *Quick reply:* keep the labels exactly `Accept` / `Refund` and `1`…`5`. The app reads the reply text.
  - *Copy code* (login code only).
- **Video header** (`pp_proof_video_*` only): upload any short .mp4 under 16 MB as the sample.
- **Login code** (`pp_otp_login_*`): Meta writes the text of authentication templates itself, so just add the
  "Copy code" button.

You don't need all 72 at once. Until a language's template is approved (and synced, step 6), devotees in that language
get the English one. So you can launch with English only and add Hindi, Tamil and Telugu later. A message type with
no approved template in any language fails (it shows as failed in Admin → Messaging). Seva, prasad and marketing
messages are only needed if you use those features.

Tip: first submit the English versions of `otp_login`, `booking_confirmed`, `puja_started` and `proof_video`, and test
them end to end (step 6). Then submit the rest.

## 5. Connect the app (Render → your API service → Environment)

**WATI**
```
MESSAGING_PROVIDER=wati
WATI_API_ENDPOINT=   # WATI → API Docs: the "API Endpoint" (looks like https://live-mt-server.wati.io/123456)
WATI_ACCESS_TOKEN=   # WATI → API Docs: the access token
WATI_WEBHOOK_TOKEN=  # make up a long random string
```
In WATI → Webhooks, add `https://YOUR-API.onrender.com/v1/webhooks/messaging/wati?token=<WATI_WEBHOOK_TOKEN>` for
message status updates and received messages.

**Gupshup**
```
MESSAGING_PROVIDER=gupshup
GUPSHUP_API_KEY=
GUPSHUP_APP_NAME=
GUPSHUP_SOURCE_NUMBER=   # the business number with country code, e.g. 919876543210
GUPSHUP_WEBHOOK_TOKEN=   # make up a long random string
```
Set the app's callback URL to
`https://YOUR-API.onrender.com/v1/webhooks/messaging/gupshup?token=<GUPSHUP_WEBHOOK_TOKEN>`.

The webhook carries delivery and read receipts plus devotees' replies (Accept/Refund on reschedules, 1–5 ratings).

## 6. Check it in the admin

1. **Admin → Messaging → Sync templates.** Statuses should turn to *approved*. Gupshup template IDs are filled in
   automatically.
2. **Test send to a staff number:** send each template to your own phone and check the text, the video and that the
   buttons open the right page.

## 7. Before taking real bookings

The live API still runs with `APP_ENV=development`, which shows login codes on screen and allows test payments.
After WhatsApp works, also:

- set up the SMS fallback for login codes: `SMS_OTP_PROVIDER=telnyx`, `SMS_OTP_API_KEY` (Telnyx API key),
  `SMS_OTP_FROM` (your Telnyx number) and optionally `SMS_OTP_MESSAGING_PROFILE_ID` (MSG91 is also supported)
- connect a real payment gateway
- then set `APP_ENV=production`
