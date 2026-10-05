"use client";
import { AsyncButton, DiyaLoader, EmptyState, IconChevronRight, StatusChip } from "@pujapath/ui";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import Link from "@/components/Link";
import { switchLocale } from "@/components/LanguageSwitcher";
import { readWishlist } from "@/components/WishlistButton";
import { LOCALES, NATIVE_NAMES, type Locale } from "@/i18n/config";
import { api } from "@/lib/client";
import { dateIST } from "@/lib/format";
import AccountGate from "./AccountGate";
import type { Me } from "./useMe";

type Booking = { id: string; code: string; status: string; title: string; temple: string; starts_at: string; image: { url: string } | null };
type Family = { id: string; name: string; relation: string | null; gotra: string | null; nakshatra: string | null };

export default function AccountHome() {
  return <div className="pp-gutter pt-6"><AccountGate>{(me, reload) => <Inner me={me} reload={reload} />}</AccountGate></div>;
}

function Inner({ me, reload }: { me: Me; reload: () => void }) {
  const t = useTranslations();
  const locale = useLocale();
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [family, setFamily] = useState<Family[]>([]);
  const [wish, setWish] = useState<{ id: number; title: string; href: string }[]>([]);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState<"profile" | "member" | null>(null);

  useEffect(() => {
    api<Booking[]>(`/account/bookings?locale=${locale}`).then(setBookings).catch(() => setBookings([]));
    api<Family[]>("/account/family").then(setFamily).catch(() => {});
    api<{ puja_ids: number[] }>("/account/wishlist").then(async (r) => {
      const ids = [...new Set([...r.puja_ids, ...readWishlist()])];
      const items = await Promise.all(ids.map((id) => api<{ id: number; slug: string; kind: string; title: string }>(`/${locale}/pujas/${id}`).catch(() => null)));
      setWish(items.filter(Boolean).map((p) => ({ id: p!.id, title: p!.title, href: `/${p!.kind === "seva" ? "sevas" : "pujas"}/${p!.id}-${p!.slug}` })));
    }).catch(() => {});
  }, [locale]);

  const saveProfile = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const newLocale = String(fd.get("locale"));
    setSubmitting("profile");
    try {
      await api("/account", { method: "PUT", json: { name: fd.get("name") || null, email: fd.get("email") || null,
        locale: newLocale, marketing_opt_in: fd.get("marketing") === "on" } });
    } finally { setSubmitting(null); }
    setSaved(true);
    reload();
    if (newLocale !== locale) switchLocale(newLocale as Locale, window.location.pathname);
  };
  const addMember = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    setSubmitting("member");
    let m: Family;
    try {
      m = await api<Family>("/account/family", { method: "POST", json: { name: fd.get("name"), relation: fd.get("relation") || null,
        gotra: fd.get("gotra") || null, nakshatra: fd.get("nakshatra") || null } });
    } finally { setSubmitting(null); }
    setFamily((f) => [...f, m]);
    form.reset();
  };

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-h1">{t("account.title")}</h1>
        <AsyncButton className="pp-btn pp-btn-secondary" onClick={async () => { await api("/auth/logout", { method: "POST" }); reload(); }}>
          {t("account.logout")}
        </AsyncButton>
      </div>
      <nav className="grid gap-3 sm:grid-cols-2">
        <Link href="/account/subscriptions" className="pp-card flex min-h-16 items-center justify-between px-4 text-ink-900 no-underline">
          {t("account.subscriptions")} <IconChevronRight className="text-gold-700" />
        </Link>
        <Link href="/account/delete" className="pp-card flex min-h-16 items-center justify-between px-4 text-ink-900 no-underline">
          {t("account.deleteAccount")} <IconChevronRight className="text-gold-700" />
        </Link>
      </nav>

      <section aria-labelledby="bk">
        <h2 id="bk" className="mb-3 text-h2">{t("account.bookings")}</h2>
        {bookings === null ? <DiyaLoader label={t("common.loading")} className="py-8" /> : bookings.length === 0 ? (
          <EmptyState title={t("account.bookingsEmpty")} action={<Link href="/pujas" className="pp-btn pp-btn-primary">{t("common.viewAll")}</Link>} />
        ) : (
          <ul className="space-y-3">
            {bookings.map((b) => (
              <li key={b.id}>
                <Link href={`/account/bookings/${b.id}`} className="pp-card flex items-center gap-3 p-3 text-ink-900 no-underline">
                  {b.image && <img src={b.image.url} alt="" className="h-16 w-16 rounded-btn object-cover" />}
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{b.title}</span>
                    <span className="block text-small text-ink-600">{b.temple} · {dateIST(b.starts_at, locale)} · {b.code}</span>
                  </span>
                  <StatusChip status={b.status} label={t(`status.${b.status}` as "status.confirmed")} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="pf" className="max-w-xl">
        <h2 id="pf" className="mb-3 text-h2">{t("account.profile")}</h2>
        <form className="pp-card space-y-3 p-4" onSubmit={saveProfile}>
          <p className="text-small text-ink-600">{t("account.phone")}: <strong className="text-ink-900">{me.phone_e164}</strong></p>
          <label className="block"><span className="mb-1 block font-medium">{t("account.name")}</span>
            <input name="name" className="pp-input" defaultValue={me.name ?? ""} autoComplete="name" /></label>
          <label className="block"><span className="mb-1 block font-medium">{t("account.email")} <span className="text-small text-ink-600">({t("common.optional")})</span></span>
            <input name="email" type="email" className="pp-input" defaultValue={me.email ?? ""} autoComplete="email" /></label>
          <label className="block"><span className="mb-1 block font-medium">{t("account.language")}</span>
            <select name="locale" className="pp-input" defaultValue={me.locale}>
              {LOCALES.map((l) => <option key={l} value={l} lang={l}>{NATIVE_NAMES[l]}</option>)}
            </select></label>
          <label className="flex min-h-12 items-center gap-3">
            <input name="marketing" type="checkbox" className="h-6 w-6 accent-[var(--gold-600)]" defaultChecked={me.marketing_opt_in} />
            {t("account.marketing")}
          </label>
          <button className="pp-btn pp-btn-primary" aria-busy={submitting === "profile" || undefined}>{t("common.save")}</button>
          {saved && <span role="status" className="ml-3 text-tulsi-600">{t("common.saved")}</span>}
        </form>
      </section>

      <section aria-labelledby="fm" className="max-w-xl">
        <h2 id="fm" className="mb-3 text-h2">{t("account.family")}</h2>
        {family.length === 0 && <p className="mb-3 text-ink-600">{t("account.familyEmpty")}</p>}
        <ul className="mb-4 space-y-2">
          {family.map((m) => (
            <li key={m.id} className="pp-card flex items-center justify-between gap-3 p-3">
              <span><span className="font-semibold">{m.name}</span> <span className="text-small text-ink-600">{[m.relation, m.gotra, m.nakshatra].filter(Boolean).join(" · ")}</span></span>
              <AsyncButton className="pp-link min-h-12" onClick={async () => {
                await api(`/account/family/${m.id}`, { method: "DELETE" });
                setFamily((f) => f.filter((x) => x.id !== m.id));
              }}>{t("common.remove")}</AsyncButton>
            </li>
          ))}
        </ul>
        <form className="pp-card grid gap-3 p-4 sm:grid-cols-2" onSubmit={addMember}>
          <p className="font-semibold sm:col-span-2">{t("account.addMember")}</p>
          <label className="block"><span className="mb-1 block text-small">{t("checkout.fullName")}</span><input name="name" required className="pp-input" /></label>
          <label className="block"><span className="mb-1 block text-small">{t("checkout.relation")}</span><input name="relation" className="pp-input" /></label>
          <label className="block"><span className="mb-1 block text-small">{t("checkout.gotra")}</span><input name="gotra" className="pp-input" /></label>
          <label className="block"><span className="mb-1 block text-small">{t("checkout.nakshatra")}</span><input name="nakshatra" className="pp-input" /></label>
          <button className="pp-btn pp-btn-secondary sm:col-span-2" aria-busy={submitting === "member" || undefined}>{t("common.add")}</button>
        </form>
      </section>

      <section aria-labelledby="wl">
        <h2 id="wl" className="mb-3 text-h2">{t("account.wishlist")}</h2>
        {wish.length === 0 ? <p className="text-ink-600">{t("account.wishlistEmpty")}</p> : (
          <ul className="flex flex-wrap gap-2">{wish.map((w) => <li key={w.id}><Link href={w.href} className="pp-chip">{w.title}</Link></li>)}</ul>
        )}
      </section>
    </div>
  );
}
