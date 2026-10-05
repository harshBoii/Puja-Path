import { GlyphLotus } from "@pujapath/ui";
import { getLocale, getTranslations } from "next-intl/server";

import { PhoneLink, WhatsAppButton, formatPhone } from "@/components/Contact";
import Link from "@/components/Link";
import { supportDays } from "@/lib/format";
import type { SiteConfig } from "@/lib/types";

export default async function Footer({ config }: { config: SiteConfig }) {
  const t = await getTranslations();
  const locale = await getLocale();
  const hours = t("footer.supportHours", {
    days: supportDays(config.support_hours.days, locale), start: config.support_hours.start, end: config.support_hours.end,
  });
  const socials = Object.entries(config.social_links).filter(([, url]) => !!url);
  return (
    <footer className="pp-marble mt-16 border-t border-gold-600 bg-marble-100 pb-24 md:pb-8">
      <div className="pp-gutter grid gap-8 py-10 md:grid-cols-3">
        <div>
          <p className="flex items-center gap-2 font-display text-h3"><GlyphLotus className="text-gold-600" />{config.brand}</p>
          <p className="mt-2 text-small text-ink-600">{t("meta.siteDescription")}</p>
        </div>
        <nav aria-label={t("footer.about")}>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-1">
            <li><Link href="/about" className="inline-flex min-h-12 items-center">{t("footer.about")}</Link></li>
            <li><Link href="/faq" className="inline-flex min-h-12 items-center">{t("footer.faq")}</Link></li>
            <li><Link href="/contact" className="inline-flex min-h-12 items-center">{t("footer.contact")}</Link></li>
            <li><Link href="/legal/terms" className="inline-flex min-h-12 items-center">{t("footer.terms")}</Link></li>
            <li><Link href="/legal/privacy" className="inline-flex min-h-12 items-center">{t("footer.privacy")}</Link></li>
            <li><Link href="/legal/refunds" className="inline-flex min-h-12 items-center">{t("footer.refunds")}</Link></li>
            <li><Link href="/legal/shipping" className="inline-flex min-h-12 items-center">{t("footer.shipping")}</Link></li>
          </ul>
        </nav>
        <div className="space-y-3">
          <p className="font-semibold">{t("footer.support")}</p>
          <p className="text-small text-ink-600">{hours}</p>
          <p>{t("footer.callUs")}: <PhoneLink e164={config.support_phone_e164} className="pp-link" /></p>
          <WhatsAppButton e164={config.whatsapp_number_e164} text={t("puja.whatsappPrefill", { title: config.brand })}
            label={`${t("footer.whatsappUs")} · ${formatPhone(config.whatsapp_number_e164)}`} />
          {socials.length > 0 && (
            <p className="text-small">{t("footer.follow")}: {socials.map(([k, url]) => (
              <a key={k} href={url} className="pp-link mr-3" rel="noopener noreferrer" target="_blank">{k}</a>
            ))}</p>
          )}
        </div>
      </div>
      <p className="pp-gutter text-small text-ink-600">{t("footer.rights", { year: new Date().getFullYear(), brand: config.brand })}</p>
    </footer>
  );
}
