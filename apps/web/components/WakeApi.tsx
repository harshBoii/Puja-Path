"use client";
import { useEffect } from "react";

/** Wakes the API host and database as soon as a visitor lands (both sleep when idle on free tiers), so they are
 *  warm by the time the visitor books. Fire-and-forget: renders nothing and never blocks or errors the page.
 *  It sits in the locale layout, which mounts once per page load, so client-side navigation doesn't repeat it. */
export default function WakeApi() {
  useEffect(() => {
    // Read the body: an unread response keeps the request (and its connection) open in Chromium.
    fetch("/api/v1/wake", { cache: "no-store" }).then((r) => r.text()).catch(() => {});
  }, []);
  return null;
}
