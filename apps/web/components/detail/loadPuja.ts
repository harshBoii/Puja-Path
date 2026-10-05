import "server-only";

import { cookies } from "next/headers";

import { getPuja } from "@/lib/api";
import type { PujaDetail } from "@/lib/types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** Published data (cached, tagged) — or, for staff with ?preview=1, the unpublished draft (uncached). */
export async function loadPuja(locale: string, id: number, preview: boolean): Promise<PujaDetail | null> {
  if (!preview) return getPuja(locale, id);
  const jar = await cookies();
  const staff = jar.get("pp_staff");
  if (!staff) return null;
  const res = await fetch(`${API_URL}/v1/admin/pujas/${id}/preview/${locale}`, {
    cache: "no-store", headers: { cookie: `pp_staff=${staff.value}` },
  });
  return res.ok ? res.json() : null;
}
