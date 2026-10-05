import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import BookingDetail from "@/components/account/BookingDetail";
import { getConfig } from "@/lib/api";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function Page({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const config = await getConfig();
  return <BookingDetail id={id} whatsapp={config.whatsapp_number_e164} />;
}
