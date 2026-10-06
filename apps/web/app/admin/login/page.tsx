"use client";
import { GlyphLotus } from "@pujapath/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field } from "@/components/admin/ui";
import { ApiError, api } from "@/lib/client";

const MESSAGES: Record<string, string> = {
  invalid_credentials: "Wrong email or password.",
  invalid_code: "That code didn't match. Use the newest code from your app, and make sure your phone's time is set automatically.",
  login_expired: "That took too long. Please sign in again.",
};
const message = (err: unknown) => (err instanceof ApiError ? MESSAGES[err.code] ?? `Something went wrong (${err.code}).` : "Network error. Check your connection and try again.");

/** Email + password, then TOTP. First login shows the authenticator secret to enrol. */
export default function AdminLogin() {
  const router = useRouter();
  const [step, setStep] = useState<"password" | "totp" | "enroll">("password");
  const [enroll, setEnroll] = useState<{ otpauth_uri: string; secret: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  return (
    <main className="pp-marble flex min-h-dvh items-center justify-center p-4">
      <div className="pp-card w-full max-w-sm space-y-4 p-6">
        <p className="flex items-center gap-2 font-display text-h2"><GlyphLotus className="text-gold-600" /> Staff sign in</p>
        {step === "password" ? (
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            setBusy(true);
            setError(null);
            try {
              const r = await api<{ step: string; otpauth_uri?: string; secret?: string }>("/admin/auth/login", {
                method: "POST", json: { email: fd.get("email"), password: fd.get("password") } });
              // "done": password-only sign-in (STAFF_2FA off). Keep the spinner until the dashboard loads.
              if (r.step === "done") { router.replace("/admin"); return; }
              if (r.step === "enroll_totp") { setEnroll({ otpauth_uri: r.otpauth_uri!, secret: r.secret! }); setStep("enroll"); }
              else setStep("totp");
              setCode("");
              setBusy(false);
            } catch (err) { setError(message(err)); setBusy(false); }
          }}>
            <Field label="Email"><input name="email" type="email" required className="pp-input" autoComplete="username" /></Field>
            <Field label="Password"><input name="password" type="password" required className="pp-input" autoComplete="current-password" /></Field>
            <button className="pp-btn pp-btn-primary w-full" disabled={busy} aria-busy={busy || undefined}>Sign in</button>
          </form>
        ) : (
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            try {
              await api("/admin/auth/totp", { method: "POST", json: { code } });
              router.replace("/admin"); // keep the spinner until the dashboard replaces this page
            } catch (err) {
              setError(message(err));
              if (err instanceof ApiError && err.code === "login_expired") setStep("password");
              setBusy(false);
            }
          }}>
            {step === "enroll" && enroll && (
              <div className="space-y-2 rounded-btn bg-gold-100 p-3 text-small">
                <p className="font-semibold">Set up two-factor authentication</p>
                <p>Add this key to Google Authenticator, Authy or 1Password, then enter the 6-digit code.</p>
                <p className="break-all font-mono text-body">{enroll.secret}</p>
                <a className="pp-link break-all" href={enroll.otpauth_uri}>Open in authenticator app</a>
              </div>
            )}
            {/* Keep digits only: apps show and copy the code as "123 456". */}
            <Field label="Authenticator code"><input name="code" inputMode="numeric" autoComplete="one-time-code" autoFocus
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              required className="pp-input text-center text-h3 tracking-[0.4em]" /></Field>
            <button className="pp-btn pp-btn-primary w-full" disabled={busy || code.length !== 6} aria-busy={busy || undefined}>Sign in</button>
            <button type="button" className="pp-link w-full text-center text-small" onClick={() => { setStep("password"); setError(null); }}>Back</button>
          </form>
        )}
        {error && <p role="alert" className="text-sindoor-600">{error}</p>}
      </div>
    </main>
  );
}
