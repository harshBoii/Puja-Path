"use client";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/client";

export type Me = { id: string; phone_e164: string; name: string | null; email: string | null; locale: string;
  marketing_opt_in: boolean; deletion_requested_at: string | null };

export function useMe() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const reload = useCallback(() => api<{ user: Me | null }>("/auth/me").then((r) => setMe(r.user)).catch(() => setMe(null)), []);
  useEffect(() => { reload(); }, [reload]);
  return { me, reload };
}
