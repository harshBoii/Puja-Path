# Puja Path

Online puja booking platform built from `materials/Online Puja Platform — PRD v1.md`.

## Layout
- `apps/api`: FastAPI, SQLAlchemy, Alembic. Providers live in `providers/{messaging,payments,shipping}` (fake, WATI, Gupshup, Razorpay, Cashfree, Shiprocket).
- `apps/worker/worker.py`: Arq worker (message dispatch, cutoff locking, AutoPay, SLA checks, expiry, reconciliation, purge).
- `apps/web`: Next.js 16 storefront (`/[locale]`) and admin (`/admin`).
- `packages/ui`: design tokens and components. `packages/locales`: en, hi, ta and te strings, checked by `scripts/check-locales.mjs`.
- `infra`: docker-compose (Postgres, Redis) and the seed art generator.

## Run locally
```
redis-server --daemonize yes
cd apps/api && uv sync && uv run alembic upgrade head && uv run python seed.py --catalog
uv run uvicorn main:app --port 8000          # API
uv run python ../worker/worker.py            # worker
cd ../web && npx -y pnpm@10 install && npx next dev -p 3000   # set API_URL in apps/web/.env.local
```
The admin login comes from `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `apps/api/.env`. TOTP is enrolled on first sign-in.

## Checks (all run in CI: `.github/workflows/ci.yml`)
- API: `cd apps/api && TEST_DATABASE_URL=postgresql://... uv run pytest`. 55 tests, covering M2–M5 acceptance on fake providers.
- Locales: `node packages/locales/scripts/check-locales.mjs`: key parity, placeholders, no literal hour counts.
- Web: `pnpm --filter @pujapath/web typecheck && pnpm --filter @pujapath/web lint`. Includes `pujapath/no-raw-internal-link`.
- Storybook: `pnpm storybook`. Tokens and components, with a locale toolbar for en/hi/ta/te.
- Against a running production build (`next build && next start`):
  - `node apps/web/scripts/script-detection.mjs`: every route per locale under 2% foreign script; zoom allowed.
  - `node apps/web/scripts/js-budget.mjs`: under 200 KB gzipped JS on listing and detail.
  - `node apps/web/e2e/journey.mjs`: browser booking from detail page to `confirmed` (`CHROME_PATH` for a local browser).
  - `npx @lhci/cli autorun` (in apps/web): mobile performance ≥ 90, accessibility ≥ 95.
- Load: `k6 run -e BASE=<staging> infra/loadtest/booking.js` (staging with fake providers only).

## Before launch
See `docs/go-live.md`. Open items:
- `temples.presiding_deity` is a single language-neutral field, so it only shows on English pages.
  Translating it means adding it to `temple_translations` (a data-model change).
- Real WATI/Gupshup, Razorpay/Cashfree and Shiprocket adapters follow their documented APIs but are untested against live accounts.
- Local Lighthouse performance scores varied 81–91 (headless Brave delays first paint even on a blank page), so the
  ≥ 90 performance target is enforced by Lighthouse CI on a clean Chromium. Accessibility scores 98–100.
# Puja-Path
