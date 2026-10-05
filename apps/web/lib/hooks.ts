"use client";
import { useSyncExternalStore } from "react";

const noop = () => () => {};

/** Reads a browser-only value (cookie, time zone, local storage) without a hydration mismatch:
 *  the server snapshot is used for SSR and the first client render, then the real value. */
export function useBrowserValue<T>(read: () => T, serverValue: T): T {
  return useSyncExternalStore(noop, read, () => serverValue);
}
