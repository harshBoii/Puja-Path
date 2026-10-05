"use client";
import { DiyaLoader } from "@pujapath/ui";
import { useTranslations } from "next-intl";

/** Shown instantly while any storefront page loads (navigation, slow API).
 *  A client component on purpose: on the server, next-intl would read request headers here, and that
 *  makes every ISR page dynamic (DYNAMIC_SERVER_USAGE). The client provider already has "common". */
export default function Loading() {
  const t = useTranslations("common");
  return <div className="pp-gutter flex min-h-[60vh] items-center justify-center"><DiyaLoader label={t("loading")} /></div>;
}
