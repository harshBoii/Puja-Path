import { EmptyState } from "@pujapath/ui";
import { useTranslations } from "next-intl";

import Link from "@/components/Link";

export default function NotFound() {
  const t = useTranslations();
  return (
    <div className="pp-gutter pt-10">
      <EmptyState title={t("common.notFoundTitle")} text={t("common.notFoundText")}
        action={<Link href="/pujas" className="pp-btn pp-btn-primary">{t("common.viewAll")}</Link>} />
    </div>
  );
}
