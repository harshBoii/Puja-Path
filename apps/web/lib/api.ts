// Server-side API access. Public catalog fetches are cached (ISR) and tagged for on-demand revalidation.
import "server-only";

import type { Home, Listing, PujaDetail, SiteConfig, TempleDetail, TempleSummary, Proof, SitemapData } from "./types";

import { apiBaseUrl } from "./api-url";

const API_URL = apiBaseUrl();

type Opts = { revalidate?: number | false; tags?: string[] };

async function get<T>(path: string, { revalidate = 60, tags = [] }: Opts = {}): Promise<T | null> {
  try {
    const res = await fetch(`${API_URL}${path}`, { next: { revalidate, tags } });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`API ${res.status} ${path}`);
    return (await res.json()) as T;
  } catch (e) {
    console.error(JSON.stringify({ level: "error", msg: "api fetch failed", path, error: String(e) }));
    throw e;
  }
}

export const getConfig = () => get<SiteConfig>("/v1/config", { revalidate: 300, tags: ["config"] }) as Promise<SiteConfig>;
export const getHome = (locale: string) => get<Home>(`/v1/${locale}/home`, { revalidate: 60, tags: ["home", "listing"] });
export const getPujas = (locale: string, qs: string) =>
  get<Listing>(`/v1/${locale}/pujas?${qs}`, { revalidate: 60, tags: ["listing"] });
export const getSevas = (locale: string, qs: string) =>
  get<Listing>(`/v1/${locale}/sevas?${qs}`, { revalidate: 60, tags: ["listing"] });
export const getPuja = (locale: string, id: number) =>
  get<PujaDetail>(`/v1/${locale}/pujas/${id}`, { revalidate: 300, tags: [`puja:${id}`] });
export const getTemples = (locale: string) =>
  get<TempleSummary[]>(`/v1/${locale}/temples`, { revalidate: 300, tags: ["listing"] });
export const getTemple = (locale: string, id: number) =>
  get<TempleDetail>(`/v1/${locale}/temples/${id}`, { revalidate: 300, tags: [`temple:${id}`, "listing"] });
export const getFaqs = (locale: string) =>
  get<{ q: string; a: string }[]>(`/v1/${locale}/faqs`, { revalidate: 300, tags: ["faq"] });
export const getCountdown = (eventId: number) =>
  get<{ show: boolean; booking_cutoff_at: string; remaining_seconds: number }>(`/v1/events/${eventId}/countdown`,
    { revalidate: 60, tags: [`event:${eventId}`] });
export const getProof = (token: string) => get<Proof>(`/v1/proof/${token}`, { revalidate: false, tags: ["proof"] });
export const getSitemap = () => get<SitemapData>("/v1/sitemap", { revalidate: 300, tags: ["listing"] });
