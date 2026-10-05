import { DiyaLoader } from "@pujapath/ui";
import { useTranslations } from "next-intl";

/** Shown instantly while any storefront page loads (navigation, slow API). */
export default function Loading() {
  const t = useTranslations("common");
  return <div className="pp-gutter flex min-h-[60vh] items-center justify-center"><DiyaLoader label={t("loading")} /></div>;
}
