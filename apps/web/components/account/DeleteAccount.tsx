"use client";
import { AsyncButton } from "@pujapath/ui";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { api } from "@/lib/client";
import { dateIST } from "@/lib/format";
import AccountGate from "./AccountGate";

export default function DeleteAccount() {
  const t = useTranslations();
  const locale = useLocale();
  const [res, setRes] = useState<{ requested_at: string; complete_by: string } | null>(null);
  return (
    <div className="pp-gutter max-w-xl pt-6">
      <AccountGate>{(me) => (
        <div className="space-y-4">
          <h1 className="text-h1">{t("account.deleteTitle")}</h1>
          <p>{t("account.deleteText")}</p>
          {res || me.deletion_requested_at ? (
            <p role="status" className="rounded-btn bg-gold-100 p-3">{t("account.deleteRequested", {
              date: dateIST(res?.requested_at ?? me.deletion_requested_at!, locale, { year: "numeric" }),
              until: dateIST(res?.complete_by ?? new Date(new Date(me.deletion_requested_at!).getTime() + 30 * 864e5).toISOString(), locale, { year: "numeric" }),
            })}</p>
          ) : (
            <AsyncButton className="pp-btn border border-sindoor-600 text-sindoor-600"
              onClick={async () => setRes(await api("/account/delete-request", { method: "POST" }))}>{t("account.deleteConfirm")}</AsyncButton>
          )}
        </div>
      )}</AccountGate>
    </div>
  );
}
