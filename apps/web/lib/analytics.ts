"use client";
// Minimal PostHog capture over fetch (~1 KB instead of the SDK), only when NEXT_PUBLIC_POSTHOG_KEY is set.
// Feeds the PRD success metric "detail to paid conversion": puja_detail_viewed -> checkout_started -> booking_confirmed.

const KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://us.i.posthog.com";

function distinctId(): string {
  try {
    let id = localStorage.getItem("pp_aid");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("pp_aid", id); }
    return id;
  } catch { return "anonymous"; }
}

export function capture(event: string, properties: Record<string, unknown> = {}) {
  if (!KEY || typeof window === "undefined") return;
  const body = JSON.stringify({ api_key: KEY, event, distinct_id: distinctId(), timestamp: new Date().toISOString(),
    properties: { ...properties, $current_url: location.href, locale: document.documentElement.lang } });
  try {
    if (!navigator.sendBeacon?.(`${HOST}/capture/`, new Blob([body], { type: "application/json" }))) {
      fetch(`${HOST}/capture/`, { method: "POST", body, keepalive: true, headers: { "Content-Type": "application/json" } }).catch(() => {});
    }
  } catch { /* analytics must never break the page */ }
}
