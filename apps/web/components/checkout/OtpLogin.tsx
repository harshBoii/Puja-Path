"use client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { ApiError, api } from "@/lib/client";

/** Phone + OTP over WhatsApp, with SMS fallback offered after 30 seconds (PRD §5.8). */
export default function OtpLogin({ initialPhone, onDone, wishlist }: { initialPhone: string; onDone: () => void; wishlist: number[] }) {
  const t = useTranslations();
  const [phone, setPhone] = useState(initialPhone || "+91");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [wait, setWait] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return;
    const id = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(id);
  }, [wait]);

  const send = async (channel: "whatsapp" | "sms") => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ dev_code?: string; sms_fallback_after_seconds: number }>("/auth/otp/request", {
        method: "POST", json: { phone_e164: phone.replace(/[^\d+]/g, ""), channel, locale: document.documentElement.lang },
      });
      setSent(true);
      setDevCode(r.dev_code ?? null);
      setWait(r.sms_fallback_after_seconds);
    } catch (e) {
      setError(e instanceof ApiError && e.code === "otp_rate_limited" ? t("checkout.otpRateLimited") : t("checkout.errorPhone"));
    } finally {
      setBusy(false);
    }
  };
  const verify = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/auth/otp/verify", { method: "POST", json: { phone_e164: phone.replace(/[^\d+]/g, ""), code,
        locale: document.documentElement.lang, wishlist } });
      onDone();
    } catch {
      setError(t("checkout.otpInvalid"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pp-card space-y-3 border border-gold-600 p-4">
      <h3 className="text-h3">{t("checkout.loginTitle")}</h3>
      {!sent ? (
        <>
          <label className="block"><span className="mb-1 block font-medium">{t("checkout.whatsapp")}</span>
            <input className="pp-input" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <button type="button" className="pp-btn pp-btn-primary w-full" disabled={busy} onClick={() => send("whatsapp")}>{t("checkout.sendCode")}</button>
        </>
      ) : (
        <>
          <p>{t("checkout.loginText", { phone })}</p>
          {devCode && <p className="rounded-btn bg-gold-100 p-2 text-small">Dev code: <strong>{devCode}</strong></p>}
          <label className="block"><span className="mb-1 block font-medium">{t("checkout.code")}</span>
            <input className="pp-input text-center text-h3 tracking-[0.4em]" inputMode="numeric" autoComplete="one-time-code"
              maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
          </label>
          <button type="button" className="pp-btn pp-btn-primary w-full" disabled={busy || code.length !== 6} onClick={verify}>{t("checkout.verify")}</button>
          {wait > 0 ? <p className="text-small text-ink-600">{t("checkout.smsIn", { seconds: wait })}</p> : (
            <button type="button" className="pp-link min-h-12" onClick={() => send("sms")}>{t("checkout.smsFallback")}</button>
          )}
        </>
      )}
      {error && <p role="alert" className="text-sindoor-600">{error}</p>}
    </div>
  );
}
