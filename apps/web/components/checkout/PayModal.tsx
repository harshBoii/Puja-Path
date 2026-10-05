"use client";
import { AsyncButton, BottomSheet } from "@pujapath/ui";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";

import { api } from "@/lib/client";

export type CheckoutPayload = {
  provider: string; booking_id: string; code: string; amount_minor: number; currency: string;
  checkout: Record<string, unknown> & { mode: string; order_id?: string };
};

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`failed to load ${src}`));
    document.head.appendChild(s);
  });
}

/** Opens the gateway checkout. The booking is confirmed only by the gateway's signed webhook; the success
 *  page polls status (PRD §8) — the browser redirect never confirms anything. */
export default function PayModal({ payload, name, phone, onPaid, onFailed, onClose }: {
  payload: CheckoutPayload; name?: string; phone: string; onPaid: () => void; onFailed: () => void; onClose: () => void;
}) {
  const t = useTranslations();
  const opened = useRef(false);
  const c = payload.checkout;

  useEffect(() => {
    if (opened.current || c.mode === "fake") return;
    opened.current = true;
    (async () => {
      try {
        if (c.mode === "razorpay") {
          await loadScript("https://checkout.razorpay.com/v1/checkout.js");
          const Rzp = (window as unknown as { Razorpay: new (o: object) => { open: () => void; on: (e: string, f: () => void) => void } }).Razorpay;
          const rzp = new Rzp({
            key: c.key, order_id: c.order_id, amount: c.amount, currency: c.currency, name: document.title,
            prefill: c.prefill ?? { name, contact: phone }, ...(c.recurring ? { recurring: "1", customer_id: c.customer_id } : {}),
            theme: { color: "#D4AF37" }, handler: onPaid, modal: { ondismiss: onClose },
          });
          rzp.on("payment.failed", onFailed);
          rzp.open();
        } else if (c.mode === "cashfree" || c.mode === "cashfree_subscription") {
          await loadScript("https://sdk.cashfree.com/js/v3/cashfree.js");
          const cf = (window as unknown as { Cashfree: (o: object) => { checkout: (o: object) => Promise<{ error?: unknown }> } })
            .Cashfree({ mode: c.env === "production" ? "production" : "sandbox" });
          const res = c.mode === "cashfree"
            ? await cf.checkout({ paymentSessionId: c.payment_session_id, redirectTarget: "_modal" })
            : await cf.checkout({ subsSessionId: c.subscription_session_id, redirectTarget: "_modal" });
          if (res?.error) onFailed(); else onPaid();
        }
      } catch {
        onFailed();
      }
    })();
  }, [c, name, phone, onPaid, onFailed, onClose]);

  if (c.mode !== "fake") return null;
  const simulate = async (outcome: "success" | "failure") => {
    await api(`/dev/fake-gateway/${c.order_id}`, { method: "POST", json: { outcome } });
    if (outcome === "success") onPaid(); else onFailed();
  };
  return (
    <BottomSheet open onClose={onClose} title={t("checkout.fakeGatewayTitle")} closeLabel={t("common.close")}
      footer={<>
        <AsyncButton className="pp-btn pp-btn-secondary flex-1" onClick={() => simulate("failure")}>{t("checkout.fakeFail")}</AsyncButton>
        <AsyncButton className="pp-btn pp-btn-primary flex-1" onClick={() => simulate("success")}>{t("checkout.fakePay")}</AsyncButton>
      </>}>
      <p>{t("checkout.fakeGatewayText")}</p>
      <p className="mt-2 font-semibold">{new Intl.NumberFormat(undefined, { style: "currency", currency: payload.currency }).format(payload.amount_minor / 100)}</p>
    </BottomSheet>
  );
}
