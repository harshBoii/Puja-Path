"use client";
import { GlyphLotus } from "@pujapath/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Field } from "@/components/admin/ui";
import { ApiError, api } from "@/lib/client";

/** Email + password, then TOTP. First login shows the authenticator secret to enrol. */
export default function AdminLogin() {
  const router = useRouter();
  const [step, setStep] = useState<"password" | "totp" | "enroll">("password");
  const [enroll, setEnroll] = useState<{ otpauth_uri: string; secret: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <main className="pp-marble flex min-h-dvh items-center justify-center p-4">
      <div className="pp-card w-full max-w-sm space-y-4 p-6">
        <p className="flex items-center gap-2 font-display text-h2"><GlyphLotus className="text-gold-600" /> Staff sign in</p>
        {step === "password" ? (
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            try {
              const r = await api<{ step: string; otpauth_uri?: string; secret?: string }>("/admin/auth/login", {
                method: "POST", json: { email: fd.get("email"), password: fd.get("password") } });
              if (r.step === "enroll_totp") { setEnroll({ otpauth_uri: r.otpauth_uri!, secret: r.secret! }); setStep("enroll"); }
              else setStep("totp");
              setError(null);
            } catch (err) { setError(err instanceof ApiError ? err.code : "error"); }
          }}>
            <Field label="Email"><input name="email" type="email" required className="pp-input" autoComplete="username" /></Field>
            <Field label="Password"><input name="password" type="password" required className="pp-input" autoComplete="current-password" /></Field>
            <button className="pp-btn pp-btn-primary w-full">Continue</button>
          </form>
        ) : (
          <form className="space-y-3" onSubmit={async (e) => {
            e.preventDefault();
            const code = String(new FormData(e.currentTarget).get("code"));
            try { await api("/admin/auth/totp", { method: "POST", json: { code } }); router.replace("/admin"); }
            catch (err) { setError(err instanceof ApiError ? err.code : "error"); }
          }}>
            {step === "enroll" && enroll && (
              <div className="space-y-2 rounded-btn bg-gold-100 p-3 text-small">
                <p className="font-semibold">Set up two-factor authentication</p>
                <p>Add this key to Google Authenticator, Authy or 1Password, then enter the 6-digit code.</p>
                <p className="break-all font-mono text-body">{enroll.secret}</p>
                <a className="pp-link break-all" href={enroll.otpauth_uri}>Open in authenticator app</a>
              </div>
            )}
            <Field label="Authenticator code"><input name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
              required className="pp-input text-center text-h3 tracking-[0.4em]" /></Field>
            <button className="pp-btn pp-btn-primary w-full">Sign in</button>
          </form>
        )}
        {error && <p role="alert" className="text-sindoor-600">{error}</p>}
      </div>
    </main>
  );
}
