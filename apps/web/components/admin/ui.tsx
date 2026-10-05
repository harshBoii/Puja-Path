"use client";
import { DiyaLoader, cx } from "@pujapath/ui";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { ApiError, api } from "@/lib/client";

export type Staff = { id: number; email: string; name: string; role: string };
const StaffCtx = createContext<Staff | null>(null);
export const useStaff = () => useContext(StaffCtx);

const NAV: { href: string; label: string; roles: string[] }[] = [
  { href: "/admin", label: "Dashboard", roles: ["*"] },
  { href: "/admin/today", label: "Today", roles: ["ops_coordinator"] },
  { href: "/admin/sla", label: "SLA board", roles: ["ops_coordinator", "support_agent"] },
  { href: "/admin/bookings", label: "Bookings", roles: ["support_agent", "ops_coordinator", "finance"] },
  { href: "/admin/assisted", label: "Assisted booking", roles: ["support_agent"] },
  { href: "/admin/catalog", label: "Catalog", roles: ["catalog_editor"] },
  { href: "/admin/temples", label: "Temples", roles: ["catalog_editor"] },
  { href: "/admin/events", label: "Events", roles: ["catalog_editor", "ops_coordinator"] },
  { href: "/admin/media", label: "Media", roles: ["catalog_editor", "ops_coordinator"] },
  { href: "/admin/faqs", label: "FAQs", roles: ["catalog_editor"] },
  { href: "/admin/shipping", label: "Shipping", roles: ["ops_coordinator"] },
  { href: "/admin/messaging", label: "Messaging", roles: ["support_agent"] },
  { href: "/admin/reviews", label: "Reviews", roles: ["support_agent", "catalog_editor"] },
  { href: "/admin/finance", label: "Finance", roles: ["finance"] },
  { href: "/admin/config", label: "Site config", roles: [] },
  { href: "/admin/staff", label: "Staff", roles: [] },
  { href: "/admin/audit", label: "Audit log", roles: [] },
];

export function AdminShell({ children }: { children: ReactNode }) {
  const [staff, setStaff] = useState<Staff | null | undefined>(undefined);
  const [menu, setMenu] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  useEffect(() => {
    api<{ staff: Staff }>("/admin/auth/me").then((r) => setStaff(r.staff)).catch(() => {
      setStaff(null);
      router.replace("/admin/login");
    });
  }, [router]);
  if (!staff) return <DiyaLoader label="Loading…" className="min-h-[60vh]" />;
  const items = NAV.filter((n) => staff.role === "admin" || n.roles.includes("*") || n.roles.includes(staff.role));
  return (
    <StaffCtx.Provider value={staff}>
      <div className="min-h-dvh md:grid md:grid-cols-[220px_1fr]">
        <aside className={cx("border-r border-marble-200 bg-surface md:block", menu ? "block" : "hidden")}>
          <p className="px-4 py-4 font-display text-h3">Admin</p>
          <nav><ul>{items.map((n) => (
            <li key={n.href}><Link href={n.href} onClick={() => setMenu(false)}
              className={cx("block min-h-11 px-4 py-2.5 no-underline", (pathname === n.href || (n.href !== "/admin" && pathname.startsWith(n.href)))
                ? "bg-gold-100 font-semibold text-ink-900" : "text-ink-600")}>{n.label}</Link></li>))}
          </ul></nav>
          <div className="border-t border-marble-200 p-4 text-small">
            <p className="font-semibold">{staff.name}</p><p className="text-ink-600">{staff.role}</p>
            <button className="pp-link mt-2" onClick={async () => { await api("/admin/auth/logout", { method: "POST" }); router.replace("/admin/login"); }}>Log out</button>
          </div>
        </aside>
        <div className="min-w-0">
          <header className="flex items-center gap-3 border-b border-marble-200 bg-surface px-4 py-3 md:hidden">
            <button className="pp-chip" onClick={() => setMenu(!menu)} aria-expanded={menu}>Menu</button>
            <span className="font-display text-h3">Admin</span>
          </header>
          <main className="p-4 md:p-6">{children}</main>
        </div>
      </div>
    </StaffCtx.Provider>
  );
}

export function PageTitle({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-h1">{children}</h1>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, children, className, actions }: { title?: ReactNode; children: ReactNode; className?: string; actions?: ReactNode }) {
  return (
    <section className={cx("pp-card mb-5 p-4", className)}>
      {(title || actions) && <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        {title && <h2 className="text-h3">{title}</h2>}{actions}</div>}
      {children}
    </section>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-small font-semibold">{label}</span>
      {children}
      {hint && <span className="text-small text-ink-600">{hint}</span>}
    </label>
  );
}

export function Table({ head, rows, empty = "Nothing here." }: { head: ReactNode[]; rows: ReactNode[][]; empty?: string }) {
  if (!rows.length) return <p className="text-ink-600">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-small">
        <thead><tr className="border-b border-marble-200">{head.map((h, i) => <th key={i} className="px-2 py-2 font-semibold">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i} className="border-b border-marble-100 align-top">{r.map((c, j) => <td key={j} className="px-2 py-2">{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export function Badge({ children, tone = "gold" }: { children: ReactNode; tone?: "gold" | "green" | "red" | "grey" }) {
  const c = { gold: "border-gold-600 text-gold-700", green: "border-tulsi-600 text-tulsi-600", red: "border-sindoor-600 text-sindoor-600",
    grey: "border-marble-400 text-ink-600" }[tone];
  return <span className={cx("inline-flex rounded-chip border bg-surface px-2 py-0.5 text-small font-semibold", c)}>{children}</span>;
}

export function statusTone(s: string): "gold" | "green" | "red" | "grey" {
  if (["completed", "proof_sent", "delivered", "read", "approved", "captured", "processed", "published", "active", "performed"].includes(s)) return "green";
  if (["cancelled", "refunded", "failed", "rejected", "breached", "returned", "disrupted", "amount_mismatch"].includes(s)) return "red";
  if (["draft", "queued", "pending"].includes(s)) return "grey";
  return "gold";
}

/** Fetch helper for admin pages: data, error, reload. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    if (!path) return;
    try { setData(await api<T>(path)); setError(null); } catch (e) { setError(e instanceof ApiError ? e.code : "error"); }
  }, [path]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount; state is set after the request resolves
  useEffect(() => { reload(); }, [reload]);
  return { data, error, reload, setData };
}

/** Runs an admin action and reports the outcome inline. */
export function useAction() {
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<unknown>, ok = "Done.") => {
    // Spin the button that started the action: the clicked button, or the submit button of the focused form.
    const el = document.activeElement;
    const btn = el instanceof HTMLButtonElement ? el : el instanceof HTMLElement ? el.closest("form")?.querySelector<HTMLButtonElement>("button:not([type=button])") : null;
    btn?.setAttribute("aria-busy", "true");
    setBusy(true);
    setMsg(null);
    try { await fn(); setMsg({ text: ok, ok: true }); return true; }
    catch (e) {
      const detail = e instanceof ApiError ? e.detail : null;
      const text = e instanceof ApiError ? (typeof detail === "object" && detail ? JSON.stringify(detail) : e.code) : String(e);
      setMsg({ text, ok: false });
      return false;
    } finally { btn?.removeAttribute("aria-busy"); setBusy(false); }
  }, []);
  const view = msg ? <p role={msg.ok ? "status" : "alert"} className={cx("my-2 break-words", msg.ok ? "text-tulsi-600" : "text-sindoor-600")}>{msg.text}</p> : null;
  return { run, busy, view };
}

export function fmtDate(iso: string | null | undefined, withTime = true) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}) }).format(new Date(iso));
}

export function inr(minor: number | null | undefined, currency = "INR") {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format((minor ?? 0) / 100);
}
