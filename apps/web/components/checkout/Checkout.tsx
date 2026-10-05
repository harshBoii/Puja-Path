"use client";
import { PriceSummary, QtyStepper, Toast, cx } from "@pujapath/ui";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import Link, { localeHref } from "@/components/Link";
import { readWishlist } from "@/components/WishlistButton";
import { ApiError, api } from "@/lib/client";
import { dateIST, money, timeIST } from "@/lib/format";
import OtpLogin from "./OtpLogin";
import PayModal, { type CheckoutPayload } from "./PayModal";

type Name = { name: string; relation: string; gotra: string; gotra_unknown: boolean; nakshatra: string };
type Addr = { name: string; phone: string; line1: string; line2: string; city: string; state: string; pincode: string };
type Draft = {
  id: string; code: string; status: string; locale: string; currency: "INR" | "USD";
  puja: { id: number; slug: string; kind: string; title: string; temple: string; image: { url: string; alt: string } | null;
    requires_nakshatra: boolean; prasad_box: string[] | null; sankalp_language: string };
  event: { id: number; starts_at: string; booking_cutoff_at: string };
  package: { id: number; code: string; max_names: number; label: string };
  names: { name: string; relation: string | null; gotra: string | null; gotra_unknown: boolean; nakshatra: string | null }[];
  whatsapp_e164: string | null; wish: string | null; addons: { id: number; qty: number }[];
  available_addons: { id: number; name: string; price_minor: number; max_qty: number; ships_home: boolean; image: { url: string } | null }[];
  prasad: boolean; address: Addr | null; dakshina_minor: number; dakshina_options: number[]; shipping_fee_minor: number;
  consent_whatsapp: boolean; consent_marketing: boolean; gotra_fallback: string; nakshatras: string[];
  pricing: { package_minor: number; addons_minor: number; shipping_minor: number; dakshina_minor: number; tax_minor: number;
    tax_lines: { label: string; amount_minor: number }[]; total_minor: number };
  seva: { occurrences: number; autopay_allowed: boolean; per_occurrence_minor: number; full_total_minor: number } | null;
  subscription_id: string | null;
};
type Family = { id: string; name: string; relation: string | null; gotra: string | null; nakshatra: string | null };

const CODES = ["+91", "+1", "+44", "+971", "+65", "+61", "+974", "+966", "+60", "+968", "+965", "+973", "+977", "+94", "+49", "+64"];
const emptyName = (): Name => ({ name: "", relation: "", gotra: "", gotra_unknown: false, nakshatra: "" });

function splitPhone(e164: string | null): { cc: string; num: string } {
  if (!e164) return { cc: "+91", num: "" };
  const cc = [...CODES].sort((a, b) => b.length - a.length).find((c) => e164.startsWith(c)) ?? "+91";
  return { cc, num: e164.slice(cc.length) };
}

export default function Checkout({ draftId }: { draftId: string }) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const search = useSearchParams();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [needLogin, setNeedLogin] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [family, setFamily] = useState<Family[]>([]);
  const [step, setStep] = useState(1);
  const [names, setNames] = useState<Name[]>([emptyName()]);
  const [phone, setPhone] = useState({ cc: "+91", num: "" });
  const [wish, setWish] = useState("");
  const [saveFamily, setSaveFamily] = useState(false);
  const [addr, setAddr] = useState<Addr>({ name: "", phone: "", line1: "", line2: "", city: "", state: "", pincode: "" });
  const [prasad, setPrasad] = useState(false);
  const [pincodeMsg, setPincodeMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [consentWa, setConsentWa] = useState(false);
  const [consentMk, setConsentMk] = useState(false);
  const [consentTerms, setConsentTerms] = useState(false);
  const [mode, setMode] = useState<"full" | "autopay">(search.get("mode") === "autopay" ? "autopay" : "full");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<{ msg: string; tone: "error" | "info" } | null>(null);
  const [busy, setBusy] = useState(false);
  const [payload, setPayload] = useState<CheckoutPayload | null>(null);

  const errText = useCallback((e: unknown) => {
    const code = e instanceof ApiError ? e.code : "generic";
    const map: Record<string, string> = {
      price_changed: "checkout.priceChanged", not_payable: "checkout.expired", nakshatra_required: "checkout.errorNakshatra",
      gotra_required: "checkout.errorGotra", whatsapp_consent_required: "checkout.errorConsent", terms_required: "checkout.errorTerms",
    };
    if (map[code]) return t(map[code] as "checkout.expired");
    return t.has(`errors.${code}`) ? t(`errors.${code}` as "errors.generic") : t("errors.generic");
  }, [t]);

  const load = useCallback(async () => {
    try {
      const d = await api<Draft>(`/drafts/${draftId}`);
      setDraft(d);
      setNeedLogin(false);
      if (d.names.length) setNames(d.names.map((n) => ({ name: n.name, relation: n.relation ?? "", gotra: n.gotra ?? "",
        gotra_unknown: n.gotra_unknown, nakshatra: n.nakshatra ?? "" })));
      setPhone(splitPhone(d.whatsapp_e164));
      setWish(d.wish ?? "");
      setPrasad(d.prasad);
      if (d.address) setAddr({ ...d.address, line2: d.address.line2 ?? "" });
      setConsentWa(d.consent_whatsapp);
      setConsentMk(d.consent_marketing);
      if (d.names.length && d.whatsapp_e164) setStep(d.status === "pending_payment" ? 3 : 2);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setNeedLogin(true);
      else setToast({ msg: errText(e), tone: "error" });
    }
  }, [draftId, errText]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount; state is set after the request resolves
    load();
    api<{ user: { phone_e164: string } | null }>("/auth/me").then((r) => {
      setLoggedIn(!!r.user);
      if (r.user) api<Family[]>("/account/family").then(setFamily).catch(() => {});
    }).catch(() => {});
  }, [load]);

  const put = async (body: Record<string, unknown>) => {
    const d = await api<Draft>(`/drafts/${draftId}`, { method: "PUT", json: body });
    setDraft(d);
    return d;
  };

  const fmt = (m: number) => money(m, draft?.currency ?? "INR", locale);
  const e164 = `${phone.cc}${phone.num.replace(/\D/g, "")}`;
  const isSeva = !!draft?.seva;

  // ---------------------------------------------------------------- step 1
  const submitNames = async () => {
    const errs: Record<string, string> = {};
    const filled = names.filter((n) => n.name.trim());
    if (!filled.length) errs["name-0"] = t("checkout.errorNames");
    names.forEach((n, i) => {
      if (!n.name.trim()) return;
      if (!n.gotra_unknown && !n.gotra.trim()) errs[`gotra-${i}`] = t("checkout.errorGotra");
      if (draft?.puja.requires_nakshatra && !n.nakshatra) errs[`nak-${i}`] = t("checkout.errorNakshatra");
    });
    if (!/^\+[1-9]\d{7,14}$/.test(e164)) errs.phone = t("checkout.errorPhone");
    setErrors(errs);
    if (Object.keys(errs).length) {
      document.getElementById(Object.keys(errs)[0])?.focus();
      return;
    }
    setBusy(true);
    try {
      await put({
        names: filled.map((n) => ({ name: n.name.trim(), relation: n.relation || null, gotra: n.gotra_unknown ? null : n.gotra.trim(),
          gotra_unknown: n.gotra_unknown, nakshatra: n.nakshatra || null })),
        whatsapp_e164: e164, wish, save_family: saveFamily && loggedIn,
      });
      setStep(isSeva ? 3 : 2);
      requestAnimationFrame(() => document.getElementById(isSeva ? "step-3" : "step-2")?.scrollIntoView({ behavior: "smooth" }));
    } catch (e) {
      setToast({ msg: errText(e), tone: "error" });
    } finally {
      setBusy(false);
    }
  };

  // ---------------------------------------------------------------- step 2
  const setAddonQty = async (id: number, qty: number) => {
    if (!draft) return;
    const next = [...draft.addons.filter((a) => a.id !== id), ...(qty ? [{ id, qty }] : [])];
    try { await put({ addons: next }); } catch (e) { setToast({ msg: errText(e), tone: "error" }); }
  };
  const needsAddress = prasad || !!draft?.addons.some((a) => draft.available_addons.find((x) => x.id === a.id)?.ships_home);
  const checkPincode = async () => {
    if (!/^\d{6}$/.test(addr.pincode)) return setPincodeMsg({ ok: false, text: t("checkout.pincodeBad") });
    const r = await api<{ serviceable: boolean }>("/serviceability", { method: "POST", json: { pincode: addr.pincode } });
    setPincodeMsg(r.serviceable ? { ok: true, text: t("checkout.pincodeOk", { pincode: addr.pincode }) }
      : { ok: false, text: t("checkout.pincodeBad") });
  };
  const submitAddons = async () => {
    setBusy(true);
    try {
      if (needsAddress) {
        const missing = (["name", "phone", "line1", "city", "state", "pincode"] as const).filter((k) => !addr[k].trim());
        if (missing.length) {
          setErrors({ address: t("checkout.errorAddress") });
          document.getElementById(`addr-${missing[0]}`)?.focus();
          return;
        }
        await put({ prasad, address: { ...addr, line2: addr.line2 || null, phone: addr.phone.replace(/[^\d+]/g, ""), country: "IN" } });
      } else {
        await put({ prasad: false });
      }
      setErrors({});
      setStep(3);
      requestAnimationFrame(() => document.getElementById("step-3")?.scrollIntoView({ behavior: "smooth" }));
    } catch (e) {
      setToast({ msg: errText(e), tone: "error" });
    } finally {
      setBusy(false);
    }
  };

  // ---------------------------------------------------------------- step 3
  const total = useMemo(() => {
    if (!draft) return 0;
    return isSeva && mode === "full" && !draft.subscription_id ? draft.pricing.total_minor * draft.seva!.occurrences : draft.pricing.total_minor;
  }, [draft, isSeva, mode]);

  const pay = async () => {
    const errs: Record<string, string> = {};
    if (!consentWa) errs.consentWa = t("checkout.errorConsent");
    if (!consentTerms) errs.consentTerms = t("checkout.errorTerms");
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      await put({ consent_whatsapp: true, consent_marketing: consentMk });
      const res = await api<CheckoutPayload>(`/drafts/${draftId}/pay`, {
        method: "POST", json: { payment_mode: mode, consent_terms: true, expected_total_minor: total },
      });
      setPayload(res);
    } catch (e) {
      setToast({ msg: errText(e), tone: "error" });
      if (e instanceof ApiError && e.code === "price_changed") load();
    } finally {
      setBusy(false);
    }
  };

  if (needLogin) {
    return (
      <div className="pp-gutter max-w-xl pt-8">
        <p className="mb-4 rounded-btn bg-gold-100 p-3">{t("checkout.assisted")}</p>
        <OtpLogin initialPhone="" onDone={() => { setLoggedIn(true); load(); }} wishlist={readWishlist()} />
      </div>
    );
  }
  if (!draft) return <div className="pp-gutter pt-8" aria-busy="true">{t("common.loading")}</div>;
  if (!["draft", "pending_payment"].includes(draft.status)) {
    return (
      <div className="pp-gutter max-w-xl pt-8">
        <p className="mb-4">{t("checkout.expired")}</p>
        <Link href="/pujas" className="pp-btn pp-btn-primary">{t("common.viewAll")}</Link>
      </div>
    );
  }

  const lines = [
    { label: t("checkout.linePackage", { package: draft.package.label }), value: fmt(draft.pricing.package_minor) },
    ...(draft.pricing.addons_minor ? [{ label: t("checkout.lineAddons"), value: fmt(draft.pricing.addons_minor) }] : []),
    ...(draft.pricing.shipping_minor ? [{ label: t("checkout.lineShipping"), value: fmt(draft.pricing.shipping_minor) }] : []),
    ...(draft.pricing.dakshina_minor ? [{ label: t("checkout.lineDakshina"), value: fmt(draft.pricing.dakshina_minor) }] : []),
    ...draft.pricing.tax_lines.map((l) => ({ label: l.label, value: fmt(l.amount_minor) })),
    ...(isSeva && mode === "full" && !draft.subscription_id ? [{ label: t("checkout.lineOccurrences", { count: draft.seva!.occurrences }), value: "" }] : []),
  ];
  const stepHead = (n: number, title: string) => (
    <h2 className="flex items-center gap-3 text-h2">
      <span className={cx("flex h-9 w-9 items-center justify-center rounded-full border text-small font-semibold",
        step >= n ? "border-gold-600 bg-gold-500 text-ink-900" : "border-marble-400 text-ink-600")}>{n}</span>
      {title}
    </h2>
  );
  const field = "mb-1 block font-medium";

  return (
    <div className="pp-gutter pt-6">
      <h1 className="text-h1">{t("checkout.title")}</h1>
      <div className="mt-4 grid gap-8 lg:grid-cols-[1fr_380px]">
        <div className="space-y-8">
          {/* summary of what is being booked */}
          <div className="pp-card flex gap-4 p-4">
            {draft.puja.image && <img src={draft.puja.image.url} alt="" className="h-20 w-20 rounded-btn object-cover" />}
            <div>
              <p className="font-semibold">{draft.puja.title}</p>
              <p className="text-small text-ink-600">{draft.puja.temple}</p>
              <p className="text-small">{dateIST(draft.event.starts_at, locale, { year: "numeric" })} · {timeIST(draft.event.starts_at, locale)} {t("common.ist")}</p>
              <p className="text-small text-ink-600">{draft.package.label} · {t("puja.names", { count: draft.package.max_names })}</p>
            </div>
          </div>

          {/* STEP 1 — sankalp details */}
          <section id="step-1" aria-labelledby="s1" className="space-y-5">
            <div id="s1">{stepHead(1, t("checkout.step1"))}</div>
            {loggedIn && family.length > 0 && (
              <div>
                <p className={field}>{t("checkout.pickFamily")}</p>
                <div className="flex flex-wrap gap-2">
                  {family.map((f) => (
                    <button key={f.id} type="button" className="pp-chip" onClick={() => setNames((ns) => {
                      const slot = ns.findIndex((n) => !n.name.trim());
                      const entry = { name: f.name, relation: f.relation ?? "", gotra: f.gotra ?? "", gotra_unknown: !f.gotra, nakshatra: f.nakshatra ?? "" };
                      if (slot >= 0) return ns.map((n, i) => (i === slot ? entry : n));
                      return ns.length < draft.package.max_names ? [...ns, entry] : ns;
                    })}>{f.name}</button>
                  ))}
                </div>
              </div>
            )}
            {names.map((n, i) => (
              <fieldset key={i} className="pp-card space-y-3 p-4">
                <legend className="px-1 font-semibold">{t("checkout.nameSlot", { n: i + 1 })}</legend>
                <label className="block"><span className={field}>{t("checkout.fullName")} {i === 0 && <span aria-hidden="true">*</span>}</span>
                  <input id={`name-${i}`} className="pp-input" value={n.name} autoComplete={i === 0 ? "name" : "off"} required={i === 0}
                    aria-invalid={!!errors[`name-${i}`]} aria-describedby={errors[`name-${i}`] ? `name-${i}-err` : undefined}
                    onChange={(e) => setNames((ns) => ns.map((x, k) => (k === i ? { ...x, name: e.target.value } : x)))} />
                </label>
                {errors[`name-${i}`] && <p id={`name-${i}-err`} className="text-sindoor-600">{errors[`name-${i}`]}</p>}
                <label className="block"><span className={field}>{t("checkout.relation")} <span className="text-small text-ink-600">({t("common.optional")})</span></span>
                  <input className="pp-input" value={n.relation} placeholder={t("checkout.relationPlaceholder")}
                    onChange={(e) => setNames((ns) => ns.map((x, k) => (k === i ? { ...x, relation: e.target.value } : x)))} />
                </label>
                <label className="block"><span className={field}>{t("checkout.gotra")}</span>
                  <input id={`gotra-${i}`} className="pp-input" list="pp-gotras" value={n.gotra} disabled={n.gotra_unknown}
                    placeholder={t("checkout.gotraPlaceholder")} aria-invalid={!!errors[`gotra-${i}`]}
                    onChange={(e) => setNames((ns) => ns.map((x, k) => (k === i ? { ...x, gotra: e.target.value } : x)))} />
                </label>
                <label className="flex min-h-12 items-center gap-3">
                  <input type="checkbox" className="h-6 w-6 accent-[var(--gold-600)]" checked={n.gotra_unknown}
                    onChange={(e) => setNames((ns) => ns.map((x, k) => (k === i ? { ...x, gotra_unknown: e.target.checked } : x)))} />
                  {t("checkout.gotraUnknown")}
                </label>
                {n.gotra_unknown && <p className="text-small text-ink-600">{t("checkout.gotraFallbackNote", { gotra: draft.gotra_fallback })}</p>}
                {errors[`gotra-${i}`] && <p className="text-sindoor-600">{errors[`gotra-${i}`]}</p>}
                <label className="block"><span className={field}>{t("checkout.nakshatra")} {!draft.puja.requires_nakshatra &&
                  <span className="text-small text-ink-600">({t("common.optional")})</span>}</span>
                  <select id={`nak-${i}`} className="pp-input" value={n.nakshatra} aria-invalid={!!errors[`nak-${i}`]}
                    onChange={(e) => setNames((ns) => ns.map((x, k) => (k === i ? { ...x, nakshatra: e.target.value } : x)))}>
                    <option value="">{t("checkout.nakshatraChoose")}</option>
                    {draft.nakshatras.map((nk) => <option key={nk} value={nk}>{nk}</option>)}
                  </select>
                </label>
                {errors[`nak-${i}`] && <p className="text-sindoor-600">{errors[`nak-${i}`]}</p>}
                {i > 0 && (
                  <button type="button" className="pp-link min-h-12" onClick={() => setNames((ns) => ns.filter((_, k) => k !== i))}>{t("common.remove")}</button>
                )}
              </fieldset>
            ))}
            <datalist id="pp-gotras">
              {["Atri", "Bharadwaja", "Gautama", "Jamadagni", "Kashyapa", "Vasishtha", "Vishvamitra", "Agastya", "Kaundinya",
                "Srivatsa", "Harita", "Shandilya", "Kaushika", "Garga", "Parashara"].map((g) => <option key={g} value={g} />)}
            </datalist>
            {names.length < draft.package.max_names && (
              <button type="button" className="pp-btn pp-btn-secondary" onClick={() => setNames((ns) => [...ns, emptyName()])}>
                + {t("checkout.nameSlot", { n: names.length + 1 })}
              </button>
            )}
            <label className="block"><span className={field}>{t("checkout.wish")} <span className="text-small text-ink-600">({t("common.optional")})</span></span>
              <textarea className="pp-input min-h-24" maxLength={140} value={wish} onChange={(e) => setWish(e.target.value)} aria-describedby="wish-help" />
              <span id="wish-help" className="text-small text-ink-600">{t("checkout.wishHelp")} {wish.length}/140</span>
            </label>
            <div>
              <span className={field} id="wa-label">{t("checkout.whatsapp")}</span>
              <div className="flex gap-2" role="group" aria-labelledby="wa-label">
                <label className="sr-only" htmlFor="cc">{t("checkout.countryCode")}</label>
                <select id="cc" className="pp-input w-28" value={phone.cc} onChange={(e) => setPhone((p) => ({ ...p, cc: e.target.value }))}>
                  {CODES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <label className="sr-only" htmlFor="phone">{t("checkout.phone")}</label>
                <input id="phone" className="pp-input" inputMode="tel" autoComplete="tel-national" value={phone.num}
                  aria-invalid={!!errors.phone} aria-describedby="phone-help"
                  onChange={(e) => setPhone((p) => ({ ...p, num: e.target.value }))} />
              </div>
              <p id="phone-help" className="text-small text-ink-600">{t("checkout.whatsappHelp")}</p>
              {errors.phone && <p className="text-sindoor-600">{errors.phone}</p>}
            </div>
            {loggedIn && (
              <label className="flex min-h-12 items-center gap-3">
                <input type="checkbox" className="h-6 w-6 accent-[var(--gold-600)]" checked={saveFamily} onChange={(e) => setSaveFamily(e.target.checked)} />
                {t("checkout.saveFamily")}
              </label>
            )}
            <p className="text-small text-ink-600">{t("checkout.purpose")}</p>
            <button type="button" className="pp-btn pp-btn-primary w-full sm:w-auto" onClick={submitNames} disabled={busy}>{t("common.continue")}</button>
          </section>

          {/* STEP 2 — add-ons (not for sevas) */}
          {!isSeva && (
            <section id="step-2" aria-labelledby="s2" className={cx("space-y-5", step < 2 && "opacity-60")}>
              <div id="s2">{stepHead(2, t("checkout.step2"))}</div>
              {step >= 2 && (
                <>
                  {draft.available_addons.length > 0 && (
                    <div className="@container">
                      <h3 className="mb-2 text-h3">{t("checkout.addons")}</h3>
                      <ul className="grid gap-3 @xl:grid-cols-2">
                        {draft.available_addons.map((a) => {
                          const q = draft.addons.find((x) => x.id === a.id)?.qty ?? 0;
                          return (
                            <li key={a.id} className="pp-card flex flex-wrap items-center gap-3 p-3">
                              {a.image && <img src={a.image.url} alt="" className="h-14 w-14 shrink-0 rounded-btn object-cover" />}
                              <div className="min-w-32 flex-1"><p className="font-semibold">{a.name}</p><p className="text-small text-ink-600">{fmt(a.price_minor)}</p></div>
                              <QtyStepper value={q} max={a.max_qty} onChange={(n) => setAddonQty(a.id, n)} label={a.name}
                                decLabel={`${t("common.remove")} ${a.name}`} incLabel={`${t("common.add")} ${a.name}`} />
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                  {draft.puja.prasad_box && (
                    <div>
                      <h3 className="mb-2 text-h3">{t("checkout.prasad")}</h3>
                      <label className="flex min-h-12 items-center gap-3">
                        <input type="checkbox" className="h-6 w-6 accent-[var(--gold-600)]" checked={prasad} onChange={(e) => setPrasad(e.target.checked)} />
                        <span>{t("checkout.prasadToggle")} <span className="text-ink-600">— {t("checkout.prasadFee", { amount: fmt(draft.shipping_fee_minor) })}</span></span>
                      </label>
                    </div>
                  )}
                  {needsAddress && (
                    <fieldset className="pp-card grid gap-3 p-4 sm:grid-cols-2">
                      {(["name", "phone", "line1", "line2", "city", "state", "pincode"] as const).map((k) => (
                        <label key={k} className={cx("block", (k === "line1" || k === "line2") && "sm:col-span-2")}>
                          <span className={field}>{t(({ name: "checkout.addressName", phone: "checkout.addressPhone", line1: "checkout.line1",
                            line2: "checkout.line2", city: "checkout.city", state: "checkout.state", pincode: "checkout.pincode" } as const)[k])}</span>
                          <input id={`addr-${k}`} className="pp-input" value={addr[k]} inputMode={k === "pincode" || k === "phone" ? "numeric" : undefined}
                            autoComplete={({ name: "name", phone: "tel", line1: "address-line1", line2: "address-line2", city: "address-level2",
                              state: "address-level1", pincode: "postal-code" } as const)[k]}
                            onChange={(e) => { setAddr((a) => ({ ...a, [k]: e.target.value })); if (k === "pincode") setPincodeMsg(null); }}
                            onBlur={k === "pincode" ? checkPincode : undefined} />
                        </label>
                      ))}
                      {pincodeMsg && <p role="status" className={pincodeMsg.ok ? "text-tulsi-600" : "text-sindoor-600"}>{pincodeMsg.text}</p>}
                      {errors.address && <p className="text-sindoor-600 sm:col-span-2">{errors.address}</p>}
                    </fieldset>
                  )}
                  {draft.dakshina_options.length > 0 && (
                    <div>
                      <h3 className="mb-2 text-h3">{t("checkout.dakshina")}</h3>
                      <div className="flex flex-wrap gap-2">
                        {[0, ...draft.dakshina_options].map((d) => (
                          <button key={d} type="button" className="pp-chip" aria-pressed={draft.dakshina_minor === d}
                            onClick={() => put({ dakshina_minor: d }).catch((e) => setToast({ msg: errText(e), tone: "error" }))}>
                            {d === 0 ? t("checkout.dakshinaNone") : fmt(d)}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <button type="button" className="pp-btn pp-btn-primary w-full sm:w-auto" onClick={submitAddons} disabled={busy}>{t("common.continue")}</button>
                </>
              )}
            </section>
          )}

          {/* STEP 3 — review and pay */}
          <section id="step-3" aria-labelledby="s3" className={cx("space-y-5", step < 3 && "opacity-60")}>
            <div id="s3">{stepHead(isSeva ? 2 : 3, t("checkout.step3"))}</div>
            {step >= 3 && (
              <>
                {isSeva && !draft.subscription_id && (
                  <fieldset>
                    <legend className="mb-2 text-h3">{t("checkout.paymentMode")}</legend>
                    {(["full", ...(draft.seva!.autopay_allowed ? ["autopay" as const] : [])] as const).map((m) => (
                      <label key={m} className={cx("mb-2 flex min-h-12 cursor-pointer items-start gap-3 rounded-card p-4",
                        mode === m ? "pp-foil-border" : "border border-gold-line bg-surface")}>
                        <input type="radio" name="mode" className="mt-1.5 h-5 w-5 accent-[var(--gold-600)]" checked={mode === m} onChange={() => setMode(m)} />
                        <span><span className="block font-semibold">{m === "full"
                          ? t("puja.payFull", { amount: fmt(draft.seva!.full_total_minor) })
                          : t("puja.payAutopay", { amount: fmt(draft.seva!.per_occurrence_minor) })}</span>
                        <span className="text-small text-ink-600">{m === "autopay" ? t("checkout.autopayNote")
                          : t("puja.totalFor", { count: draft.seva!.occurrences, amount: fmt(draft.seva!.full_total_minor) })}</span></span>
                      </label>
                    ))}
                  </fieldset>
                )}
                <div className="lg:hidden"><PriceSummary lines={lines} totalLabel={t("checkout.total")} total={fmt(total)} note={t("checkout.totalNote")} /></div>
                <div className="space-y-2">
                  <label className="flex items-start gap-3 py-2">
                    <input type="checkbox" className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--gold-600)]" checked={consentWa}
                      aria-invalid={!!errors.consentWa} onChange={(e) => setConsentWa(e.target.checked)} />
                    <span>{t("checkout.consentWhatsapp")}<span className="block text-small text-ink-600">{t("checkout.consentWhatsappNote")}</span></span>
                  </label>
                  {errors.consentWa && <p className="text-sindoor-600">{errors.consentWa}</p>}
                  <label className="flex items-start gap-3 py-2">
                    <input type="checkbox" className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--gold-600)]" checked={consentMk} onChange={(e) => setConsentMk(e.target.checked)} />
                    <span>{t("checkout.consentMarketing")}</span>
                  </label>
                  <label className="flex items-start gap-3 py-2">
                    <input type="checkbox" className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--gold-600)]" checked={consentTerms}
                      aria-invalid={!!errors.consentTerms} onChange={(e) => setConsentTerms(e.target.checked)} />
                    <span>{t("checkout.consentTerms", { terms: "\u0001", refunds: "\u0002" }).split(/(\u0001|\u0002)/).map((part, i) =>
                      part === "\u0001" ? <Link key={i} href="/legal/terms" className="pp-link" target="_blank">{t("footer.terms")}</Link>
                        : part === "\u0002" ? <Link key={i} href="/legal/refunds" className="pp-link" target="_blank">{t("footer.refunds")}</Link>
                          : part)}</span>
                  </label>
                  {errors.consentTerms && <p className="text-sindoor-600">{errors.consentTerms}</p>}
                </div>
                {!loggedIn ? (
                  <OtpLogin initialPhone={e164} wishlist={readWishlist()} onDone={() => setLoggedIn(true)} />
                ) : (
                  <button type="button" className="pp-btn pp-btn-primary w-full text-h3" onClick={pay} disabled={busy}>
                    {t("checkout.pay", { amount: fmt(total) })}
                  </button>
                )}
              </>
            )}
          </section>
        </div>

        <aside className="hidden lg:block">
          <div className="sticky top-24 space-y-3">
            <PriceSummary lines={lines} totalLabel={t("checkout.total")} total={fmt(total)} note={t("checkout.totalNote")} />
          </div>
        </aside>
      </div>

      {payload && (
        <PayModal payload={payload} name={names[0]?.name} phone={e164} onClose={() => setPayload(null)}
          onPaid={() => router.push(localeHref(locale, `/bookings/${draftId}/success`))}
          onFailed={() => { setPayload(null); setToast({ msg: t("checkout.paymentFailed"), tone: "error" }); }} />
      )}
      <Toast message={toast?.msg ?? null} tone={toast?.tone} onDone={() => setToast(null)} />
    </div>
  );
}
