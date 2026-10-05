import { GlyphLotus } from "@pujapath/ui";
import { getLocale, getTranslations } from "next-intl/server";

import { WhatsAppButton } from "@/components/Contact";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import Link from "@/components/Link";
import type { Locale } from "@/i18n/config";
import type { SiteConfig } from "@/lib/types";

export default async function Header({ config }: { config: SiteConfig }) {
  const t = await getTranslations();
  const locale = (await getLocale()) as Locale;
  return (
    <header className="sticky top-0 z-40 border-b border-marble-200 bg-marble-50/95">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:bg-surface focus:p-2">
        {t("nav.skipToContent")}
      </a>
      <div className="pp-gutter flex h-16 items-center gap-3 md:h-20">
        <Link href="/" className="flex items-center gap-2 text-ink-900 no-underline">
          <GlyphLotus size={30} className="text-gold-600" />
          <span className="font-display text-h3 font-semibold">{config.brand}</span>
        </Link>
        <nav aria-label={t("nav.mainNav")} className="ml-6 hidden md:block">
          <ul className="flex gap-1">
            <li><Link href="/pujas" className="pp-chip border-transparent bg-transparent no-underline">{t("nav.pujas")}</Link></li>
            <li><Link href="/sevas" className="pp-chip border-transparent bg-transparent no-underline">{t("nav.sevas")}</Link></li>
            <li><Link href="/temples" className="pp-chip border-transparent bg-transparent no-underline">{t("nav.temples")}</Link></li>
            <li><Link href="/account" className="pp-chip border-transparent bg-transparent no-underline">{t("nav.account")}</Link></li>
          </ul>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <LanguageSwitcher current={locale} label={t("nav.language")} />
          <WhatsAppButton e164={config.whatsapp_number_e164} text={t("puja.whatsappPrefill", { title: config.brand })}
            label={t("nav.needHelp")} className="pp-btn pp-btn-whatsapp hidden px-3 sm:inline-flex" />
        </div>
      </div>
    </header>
  );
}
