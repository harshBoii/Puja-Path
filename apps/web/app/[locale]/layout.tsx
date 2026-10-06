import "../globals.css";

import type { Metadata, Viewport } from "next";
import { notFound } from "next/navigation";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";

import BottomTabBar from "@/components/BottomTabBar";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import { CURRENCY_SCRIPT } from "@/components/Price";
import { NavOverlay } from "@/components/NavPending";
import Providers from "@/components/Providers";
import WakeApi from "@/components/WakeApi";
import SwRegister from "@/components/SwRegister";
import { LOCALES, isLocale } from "@/i18n/config";
import { getConfig } from "@/lib/api";
import { fontsFor } from "@/lib/fonts";
import { SITE } from "@/lib/seo";

const CLIENT_NAMESPACES = ["common", "nav", "footer", "venue", "puja", "checkout", "success", "account", "status", "timeline",
  "errors"] as const;

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

// Pinch-zoom always allowed (PRD §4, §12): no maximumScale / userScalable here.
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#FBF9F5" };

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale });
  const config = await getConfig();
  return {
    metadataBase: new URL(SITE),
    title: { default: t("meta.homeTitle", { brand: config.brand }), template: `%s · ${config.brand}` },
    description: t("meta.siteDescription"),
    manifest: "/manifest.webmanifest",
    icons: { icon: "/icon-192.png", apple: "/icon-192.png" },
    robots: process.env.APP_ENV === "staging" ? { index: false, follow: false } : undefined,
  };
}

export default async function LocaleLayout({ children, params }: { children: React.ReactNode; params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  setRequestLocale(locale);
  const [config, t, messages] = await Promise.all([getConfig(), getTranslations(), getMessages()]);
  // Only the namespaces client components use go to the browser (keeps legal/marketing copy out of the payload).
  const clientMessages = Object.fromEntries(CLIENT_NAMESPACES.map((ns) => [ns, messages[ns]]));
  const fonts = fontsFor(locale);
  return (
    <html lang={locale} className={fonts.className} style={fonts.style} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: CURRENCY_SCRIPT }} />
      </head>
      <body className="min-h-dvh">
        <NextIntlClientProvider messages={clientMessages}>
          <Providers>
            <Header config={config} />
            <main id="main" className="pb-20 md:pb-0">{children}</main>
            <Footer config={config} />
            <BottomTabBar labels={{ home: t("nav.home"), pujas: t("nav.pujas"), sevas: t("nav.sevas"),
              account: t("nav.account"), nav: t("nav.tabBar") }} />
          </Providers>
          <NavOverlay />
          <WakeApi />
          <SwRegister />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
