"use client";
// Instant feedback on navigation. Links don't prefetch (performance budget), so after a click the old page
// would sit still until the server answers. Every Link and programmatic navigation reports its pending
// state here, and <NavOverlay> shows the diya loader at once.
import { DiyaLoader } from "@pujapath/ui";
// eslint-disable-next-line pujapath/no-raw-internal-link -- only the hook, not a link
import { useLinkStatus } from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useSyncExternalStore, useTransition } from "react";

let count = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };

/** Marks a navigation as started; call the returned function when it ends. */
export function beginNav(): () => void {
  count += 1;
  emit();
  let done = false;
  return () => { if (!done) { done = true; count -= 1; emit(); } };
}

function usePendingReport(pending: boolean) {
  useEffect(() => (pending ? beginNav() : undefined), [pending]);
}

/** Rendered inside every <Link>: reports that link's pending navigation. */
export function LinkPending() {
  usePendingReport(useLinkStatus().pending);
  return null;
}

/** router.push / replace that shows the loader until the new page is on screen. */
export function usePendingRouter() {
  const router = useRouter();
  const [pending, start] = useTransition();
  usePendingReport(pending);
  return {
    push: useCallback((href: string, opts?: { scroll?: boolean }) => start(() => router.push(href, opts)), [router]),
    replace: useCallback((href: string, opts?: { scroll?: boolean }) => start(() => router.replace(href, opts)), [router]),
  };
}

export function NavOverlay() {
  const t = useTranslations("common");
  const active = useSyncExternalStore(subscribe, () => count > 0, () => false);
  if (!active) return null;
  return (
    <div className="pp-nav-overlay fixed inset-0 z-[60] flex items-center justify-center" aria-live="polite">
      <div className="pp-nav-bar absolute inset-x-0 top-0 h-1" />
      <DiyaLoader label={t("loading")} />
    </div>
  );
}
