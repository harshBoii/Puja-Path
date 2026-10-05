import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import { getConfig } from "@/lib/api";
import Success from "./Success";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function SuccessPage({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const config = await getConfig();
  return <div className="pp-gutter pt-8"><Success id={id} slaHours={config.video_sla_hours_default} /></div>;
}
