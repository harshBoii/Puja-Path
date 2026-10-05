// Works in server and client trees (next-intl hooks support both).
import { PujaCard } from "@pujapath/ui";
import { useLocale, useTranslations } from "next-intl";

import Price from "@/components/Price";
import WishlistButton from "@/components/WishlistButton";
import { dateIST, pujaPath, timeIST } from "@/lib/format";
import type { PujaCardData } from "@/lib/types";

export default function PujaCardItem({ p, featured }: { p: PujaCardData; featured?: boolean }) {
  const t = useTranslations();
  const locale = useLocale();
  return (
    <PujaCard
      href={pujaPath(p)}
      image={p.image}
      chip={p.occasion_chip}
      title={p.title}
      temple={`${p.temple.name}, ${p.temple.city}`}
      venue={t(`venue.${p.temple.venue_type}`)}
      dateLabel={p.event ? `${dateIST(p.event.starts_at, locale)} · ${timeIST(p.event.starts_at, locale)} ${t("common.ist")}` : undefined}
      priceLabel={<Price prices={p.from_prices} template={(s) => t("common.from", { price: s })} />}
      bookLabel={t("common.book")}
      featured={featured}
      action={<WishlistButton pujaId={p.id} labels={{ add: t("common.wishlistAdd"), remove: t("common.wishlistRemove") }} />}
    />
  );
}
