"use client";
import { IconHeart } from "@pujapath/ui";
import { useState } from "react";

import { useBrowserValue } from "@/lib/hooks";

const KEY = "pp_wishlist";

export function readWishlist(): number[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

/** Works logged out (local storage); synced to the account at login and on each tap when logged in. */
export default function WishlistButton({ pujaId, labels }: { pujaId: number; labels: { add: string; remove: string } }) {
  const stored = useBrowserValue(() => readWishlist().includes(pujaId), false);
  const [toggled, setToggled] = useState<boolean | null>(null);
  const on = toggled ?? stored;
  const toggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const list = readWishlist();
    const next = on ? list.filter((x) => x !== pujaId) : [...new Set([...list, pujaId])];
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* private mode */ }
    setToggled(!on);
    fetch(`/api/v1/account/wishlist/${pujaId}`, { method: on ? "DELETE" : "PUT", credentials: "same-origin" }).catch(() => {});
  };
  return (
    <button type="button" onClick={toggle} aria-pressed={on} aria-label={on ? labels.remove : labels.add}
      className="flex h-12 w-12 items-center justify-center rounded-full bg-surface/90 text-sindoor-600 shadow-card">
      <IconHeart size={22} filled={on} />
    </button>
  );
}
