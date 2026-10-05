"use client";
import { useTranslations } from "next-intl";

import OtpLogin from "@/components/checkout/OtpLogin";
import { readWishlist } from "@/components/WishlistButton";
import { type Me, useMe } from "./useMe";

/** Session lives in an httpOnly cookie (90 days); without it, log in by WhatsApp OTP. */
export default function AccountGate({ children }: { children: (me: Me, reload: () => void) => React.ReactNode }) {
  const t = useTranslations();
  const { me, reload } = useMe();
  if (me === undefined) return <p aria-busy="true">{t("common.loading")}</p>;
  if (!me) {
    return (
      <div className="max-w-md space-y-3">
        <h1 className="text-h1">{t("account.login")}</h1>
        <p className="text-ink-600">{t("account.loginText")}</p>
        <OtpLogin initialPhone="" wishlist={readWishlist()} onDone={reload} />
      </div>
    );
  }
  return <>{children(me, reload)}</>;
}
