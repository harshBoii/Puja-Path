import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { CallButton, PhoneLink, WhatsAppButton } from "@/components/Contact";
import { NATIVE_NAMES, type Locale } from "@/i18n/config";
import { getConfig } from "@/lib/api";
import { supportDays } from "@/lib/format";
import { alternates } from "@/lib/seo";

export const revalidate = 3600;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale });
  return { title: t("pages.contactTitle"), alternates: alternates(locale, "/contact") };
}

export default async function Contact({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, c] = await Promise.all([getTranslations(), getConfig()]);
  return (
    <div className="pp-gutter max-w-3xl space-y-5 pt-6">
      <h1 className="text-h1">{t("pages.contactTitle")}</h1>
      <p>{t("pages.contactBody", { days: supportDays(c.support_hours.days, locale), start: c.support_hours.start,
        end: c.support_hours.end, languages: c.support_languages.map((l) => NATIVE_NAMES[l as Locale] ?? l).join(", ") })}</p>
      <p>{t("footer.callUs")}: <PhoneLink e164={c.support_phone_e164} className="pp-link" /></p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <WhatsAppButton e164={c.whatsapp_number_e164} text={t("puja.whatsappPrefill", { title: c.brand })} label={t("footer.whatsappUs")} showNumber />
        <CallButton e164={c.support_phone_e164} label={t("footer.callUs")} />
      </div>
    </div>
  );
}
