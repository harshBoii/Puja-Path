# Puja Path

Online puja booking platform built from `materials/Online Puja Platform — PRD v1.md`.

## Layout
- `apps/api`: FastAPI, SQLAlchemy, Alembic. Providers live in `providers/{messaging,payments,shipping}` (fake, WATI, Gupshup, Razorpay, Cashfree, Shiprocket).
- Background jobs (message dispatch, cutoff locking, AutoPay, SLA checks, payment expiry, reconciliation, purge) live in
  `apps/api/services/tasks.py`. `JOBS_MODE=inline` (default) runs them inside the API, with no Redis and no worker.
  `JOBS_MODE=worker` runs them on the Arq worker (`apps/worker/worker.py`) with Redis instead.
- `apps/web`: Next.js 16 storefront (`/[locale]`) and admin (`/admin`).
- `packages/ui`: design tokens and components. `packages/locales`: en, hi, ta and te strings, checked by `scripts/check-locales.mjs`.
- `infra`: docker-compose (Postgres, Redis) and the seed art generator.

## Run locally
```
cd apps/api && uv sync && uv run alembic upgrade head && uv run python seed.py --catalog
uv run uvicorn main:app --port 8000          # API (also runs background jobs with JOBS_MODE=inline)
cd ../web && npx -y pnpm@10 install && npx next dev -p 3000   # set API_URL in apps/web/.env.local
```
The admin login comes from `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `apps/api/.env`. TOTP is enrolled on first sign-in.

## Demo photos
`apps/api/scripts/fetch_images.py` replaces the SVG demo art with Pexels photos (alt text in all four languages,
photographer credits in `apps/web/public/images/photos/CREDITS.json`). With the `R2_*` variables set, it uploads to
Cloudflare R2; otherwise it saves into `apps/web/public/images/photos/`.
```
cd apps/api
PEXELS_API_KEY=... uv run python scripts/fetch_images.py   # download, writes seed_images.json
uv run python scripts/fetch_images.py --apply              # update the database (DATABASE_URL)
```
These are stand-ins: replace them with partner-temple photography before launch.

## Deploy
- **Backend on Render:** New > Blueprint, pick this repo (`render.yaml`). It pins Python 3.12, installs
  `apps/api/requirements.txt`, runs migrations on start, and uses `JOBS_MODE=inline` (no Redis or worker).
  Fill in the `sync: false` variables (Neon `DATABASE_URL`, site URLs, `REVALIDATE_SECRET`, admin login).
  If you change Python dependencies, regenerate the file:
  `cd apps/api && uv export --no-dev --no-hashes --no-emit-project -o requirements.txt`.
- **Website on Vercel:** Root Directory `apps/web`. Set `API_URL` (the Render URL; `https://` is added if missing),
  `NEXT_PUBLIC_SITE_URL` and `REVALIDATE_SECRET` (same value as the API). Deploy the backend first: the build
  fetches site config and pre-renders pages from the API.

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
